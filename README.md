# ![](resources/logo/32x32.png) ParametricText

ParametricText is an Autodesk® Fusion 360™ add-in for creating *Text Parameters* in sketches - as far as it can be done.

Text parameters can be created in two ways:

* Custom text entered in the *Change Text Parameters* dialog
* Using the comment of Fusion 360™ *User Parameters*

All parameters are stored within in the document upon save. The texts are always "rendered" in the sketches, so they can be viewed without having the add-in. However, to correctly update the values, the add-in is needed.

![Screenshot](screenshot.png)

## Installation
Download the add-in from the [Releases](https://github.com/thomasa88/ParametricText/releases) page.

Unpack it into `API\AddIns` (see [How to install an add-in or script in Fusion 360](https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html)).

Make sure the directory is named `ParametricText`, with no suffix.

## Usage

Press Shift+S in Fusion 360™ and go to the *Add-Ins* tab. Then select the add-in and click the *Run* button. Optionally select *Run on Startup*.

To parameterize texts, create sketches with Text features. Make sure to enter some dummy text, to make the Text features easier to select.

Open the *Modify* menu under e.g. the *SOLID* tab and click *Change Text Parameters*.

Use the + and x symbols to add and remove rows from the table. To specify what sketch texts to affect, click the desired row and then select the sketch texts in the design.

Select to use a *Custom Text*, entered in the text field to the right, or the comment of a *User Parameter*, as defined *Change Parameters* in the *Modify* menu.

## Special keywords

The following special keywords are replaced with text dynamically by the add-in:

| Keyword         | Description                                                  |
| --------------- | ------------------------------------------------------------ |
| &lt;version&gt; | The current version of the file. The value is updated just before the file is saved, to reflect the correct value in the saved file.<br /><br />Example: *23* |

## Known Limitations

* Assigning text to sketch texts with negative angles result in error ([Fusion 360™ bug](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-unable-to-modify-text-of-a-sketchtext-created-manually-with/m-p/9502107/highlight/true#M10086)).
  * Workaround is to specify a positive angle. That is, `-90` becomes `360-90 = 270`. It might be hard to change `-180` to `180` without entering another positive value in-between.
* Any horizontal or vertical flip of the text is removed when assigning texts ([Fusion 360™ bug](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/sketchtext-object/m-p/8562981/highlight/true#M7276)).
* *Compute All* does not update the text parameters.

## Author

This add-in is created by Thomas Axelsson.

## License

This project is licensed under the terms of the MIT license. See [LICENSE](LICENSE).

## Changelog

* v0.1.0
  * First beta release