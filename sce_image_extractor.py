import argparse
import enum
import io
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Generator, NamedTuple

import requests
from PIL import Image

newline = '\n'
r_source_repo = re.compile(
    r"SOURCE_REPO\s?=\s?'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'"
)


class Args(NamedTuple):
  data: Path
  output: Path
  filters: set[str]
  overwrite: bool


class Face(enum.Enum):
  FRONT = 0
  BACK = 1


class Card(NamedTuple):
  id: str
  name: str
  parents: Path
  images: dict[Face, str | None]
  height: int
  width: int
  index: int


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument('--output',
                      type=Path, default='./cards/', help='Output path')
  parser.add_argument('--filters',
                      type=str, nargs='*', help='Filter cards. Supports * wildcard')
  parser.add_argument('--overwrite',
                      type=bool, default=True, help='Overwrite existing cards')
  parser.add_argument('data',
                      type=Path, help='json data')

  args = parser.parse_args()
  return Args(
      data=args.data,
      output=args.output,
      overwrite=args.overwrite,
      filters=args.filters,
  )


def file_ext(image: Image.Image):
  if image.format == "JPEG":
    return ".jpg"
  elif image.format == "PNG":
    return ".png"
  else:
    raise ValueError(image.format)


def get_card_index(deck_id: str, card_id: str):
  if not card_id.startswith(deck_id):
    raise ValueError()

  return int(card_id[len(deck_id):])


def find_cards(url: str, data: dict, parents: Path) -> Generator[Card, None, None]:
  for item in data:
    notes = item["GMNotes"]
    if notes.endswith(".json"):
      content_data = requests.get(f"{url}/{notes}").json()
      yield from find_cards(url, content_data["ContainedObjects"], Path(notes).with_suffix(''))
    elif item.get("Name") in ("Card", "CardCustom") and notes:
      try:
        card_data = json.loads(notes)
        image_data = next(iter(item["CustomDeck"].items()))
        yield Card(
            id=card_data["id"],
            name=item["Nickname"],
            parents=parents,
            images={
                Face.FRONT: image_data[1]["FaceURL"],
                Face.BACK: image_data[1]["BackURL"] if image_data[1]["UniqueBack"] else None,
            },
            height=image_data[1]["NumHeight"],
            width=image_data[1]["NumWidth"],
            index=get_card_index(image_data[0], str(item["CardID"])),
        )
      except:
        pass
    if "ContainedObjects" in item:
      yield from find_cards(url, item["ContainedObjects"], parents)


def download_image(card, image_url: str, temp_files: dict[str, Path]):
  width = card.width
  height = card.height
  single_image = width == 1 and height == 1

  if image_url in temp_files:
    image_fp = temp_files[image_url]
  else:
    image_fp = io.BytesIO(requests.get(image_url).content)
    if not single_image:
      with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(image_fp.getvalue())
        temp_files[image_url] = Path(tmp.name)

  return image_fp


def get_filename(path: Path, card: Card, face: Face):
  if card.parents:
    path = path / card.parents
  return path / f"{card.id}_{face.name.lower()}"


def save_image(filename: Path, card: Card, image_fp: io.BytesIO | Path):
  width = card.width
  height = card.height
  index = card.index
  x = index % width
  y = index // width

  image = Image.open(image_fp)
  crop_width = image.width // width
  crop_height = image.height // height
  crop_x = x * crop_width
  crop_y = y * crop_height

  cropped_image = image.crop(
      (crop_x, crop_y, crop_x + crop_width, crop_y + crop_height)
  )

  filename = filename.with_suffix(file_ext(image))
  filename.parent.mkdir(parents=True, exist_ok=True)
  cropped_image.save(filename)


def matches_filter(card: Card, filters: set[str]):
  return any((
      card.parents.match(filter)
      for filter in filters
  ))


def extract_source_url(json_data) -> str | None:
  match = r_source_repo.search(json_data['LuaScript'])
  if not match:
    return None

  return match[1]


def main(args: Args):
  with args.data.open() as f:
    json_data = json.load(f)

  source_url = extract_source_url(json_data)
  if not source_url:
    print(f'Source url not found')
    return

  temp_files = dict[str, Path]()
  try:
    cards = [
        card
        for card in find_cards(source_url, json_data["ObjectStates"], Path('players'))
    ]
    print(f'Cards: {len(cards)}')

    if args.filters:
      filtered_cards = [
          card
          for card in cards
          if matches_filter(card, args.filters)
      ]
      print(f'Filtered cards: {len(filtered_cards)}')
    else:
      filtered_cards = cards

    found_filters = sorted({
        f'{newline}  - {str(card.parents)}'
        for card in cards
    })
    print(f"Filters: {''.join(found_filters)}")

    for card in filtered_cards:
      for face in Face:
        image_url = card.images.get(face)
        if image_url is None:
          continue

        filename = get_filename(args.output, card, face)
        if not args.overwrite and filename.exists():
          continue

        image_fp = download_image(card, image_url, temp_files)
        save_image(filename, card, image_fp)

    with (args.output / 'cards.json').open('w') as f:
      json.dump(
          [
              {
                  "id": card.id,
                  "name": card.name,
              }
              for card in filtered_cards
          ],
          f,
          indent=2,
          sort_keys=True,
      )
  finally:
    for file in temp_files.values():
      os.remove(file)


if __name__ == '__main__':
  main(parse_args())
