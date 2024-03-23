<a href="https://apps.autodesk.com/FUSION/en/Detail/Index?id=2114937992453312456&amp;appLang=en&amp;os=Win64"><img align=right src="https://badgen.net/runkit/thomasa88/autodesk-rating-badge/branches/master/2114937992453312456"></a>

Maintenance level: 🟢 Updates happen occasionally. Critical bugs get fixed.

# ![](resources/logo/32x32.png) ParametricText

ParametricText is an Autodesk® Fusion 360™ add-in for creating *Text Parameters* in sketches.

![Screenshot](docs/images/screenshot.png)

## Supported Platforms

* Windows
* Mac OS

## Documentation

https://parametrictext.readthedocs.io/en/stable/

## More Fusion 360™ Add-ins

[My Fusion 360™ app store page](https://apps.autodesk.com/en/Publisher/PublisherHomepage?ID=JLH9M8296BET)

[All my add-ins on Github](https://github.com/topics/fusion-360?q=user%3Athomasa88)

## Development

### Building the documentation

```
cd doc
python3 -m venv venv # First time
venv/bin/activate
python3 -m pip install -r requirements.txt # First time
make html
ls _build/html
```

### Running tests

Currently, each unit test file is self-contained. Just execute each file with Python.
