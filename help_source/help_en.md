# Help

## Usage

1. Launch `PythonPackageDownloader`

1. Enter download information

    Screen items are as follows:

    | Screen Item | Description |
    | ---- | ---- |
    | Download Method | Required<br>If PyPISimple and requests are not installed, pip will be used forcibly.<br>Use pip: Download packages using pip download with the pip in the download environment<br>Don't use pip: Download packages using HTTP |
    | Select OS | Select Windows, Linux, or macOS |
    | Python Version | Required, multiple selection allowed<br>Select the target Python version |
    | Package List | Required<br>Specify the path to the package list (text file)<br>The format is the same as `requirements.txt` used in `pip install -r requirements.txt` |
    | Download Destination | Required<br>Specify the download destination folder.<br>Default is the downloads folder in the script location |
    | pip Path | Required when using pip<br>Searches for pip in the download environment and displays it initially |
    | Use Proxy<br>User ~ Port | Optional<br>Enter if using a proxy |
    | Include Source Format | Optional<br>If download fails, attempt to download tar.gz format |  
    | Download Dependencies | Check dependencies of downloaded packages and download recursively<br>Note that processing time may increase depending on the package |

    > Press the "Save Settings" button to save the input items

1. Press the "Start Download" button
