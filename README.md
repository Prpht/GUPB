# GUPB

Gra Udająca Prawdziwe Battle-Royale (polish for "Game Pretending to be a True Battle-Royale").

A simplified action game used for teaching machine learning courses at AGH University of Science and Technology.

## Requirements

The projects requires Python 3.8 or higher.

## Installation

When in project root directory install the requirements using the following command.
Using `virtualenv` is recommended, as it will allow to isolate the installed dependencies from main environment.
```
pip install -r requirements.txt
```

## Usage

To run the game type `python -m gupb` while in root directory.
Additional options are covered in the help excerpt below.
```
Usage: python -m gupb [OPTIONS]

Options:
  -c, --config_path PATH    The path to run configuration file.
  -i, --inquiry             Whether to configure the runner interactively on
                            start.

  -l, --log_directory PATH  The path to log storage directory.
  --help                    Show this message and exit.
```
When no configuration file provided, `gupb\default_config.py` is used instead.
Options selected as default in interactive mode are based on chosen configuration.
Log are stored in `results` directory by default.



 