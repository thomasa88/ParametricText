# ![](resources/logo/32x32.png) ParametricText

ParametricText is an Autodesk® Fusion add-in for creating *Text Parameters* in sketches.

![Screenshot](docs/images/screenshot.png)

## Supported Platforms

* Windows
* Mac OS

## Documentation

https://parametrictext.readthedocs.io/en/stable/

## More Fusion Add-ins

[My Fusion app store page](https://apps.autodesk.com/en/Publisher/PublisherHomepage?ID=JLH9M8296BET)

[All my add-ins on Github](https://github.com/topics/fusion-360?q=user%3Athomasa88)

## Development

### Building the documentation

```
cd doc
python3 -m venv venv # First time
. venv/bin/activate
python3 -m pip install -r requirements.txt # First time
make html
ls _build/html
```

### Running tests

Run `python3 -m unittest` to execute all unit tests.