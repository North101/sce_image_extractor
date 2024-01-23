# SCE Image Extractor

## The script

### Required installs

[Python 3](https://wiki.python.org/moin/BeginnersGuide/Download)

Download [this repo](https://codeload.github.com/North101/sce_image_extractor/zip/refs/heads/master) and unzip it


```bash
# setup python virtual env
python3 -m venv .venv

# activate virtual env
source .venv/bin/activate

# install required libs
python3 -m pip install -r requirements.txt
```


### Running

Activate python virtual env (if not already done)
```bash
source .venv/bin/activate
```

Extract images with the default arguments:
```bash
python sce_image_extractor.py path/to/forbidden_knowledge.json
```

To see all the arguments:
```bash
python sce_image_extractor.py --help
```
