# CDR Reader

A small local web app for viewing CorelDRAW `.cdr` files. It asks Inkscape to convert the selected file to PDF and displays that PDF in your browser. The file and converted PDF stay on your computer; the app does not upload them to a service.

## Requirements

- Python 3 (no third-party Python packages required)
- Inkscape installed, with its `inkscape` command available on your PATH

On macOS, install Inkscape from [inkscape.org](https://inkscape.org/). If the command is not on your PATH, add the Inkscape application bundle's `Contents/MacOS` folder to PATH before launching the app.

## Run

```bash
python3 app.py
```

The app opens `http://127.0.0.1:8765` in your browser. Choose a `.cdr` file to view it. Conversion support depends on the CDR version and features supported by your Inkscape installation. Uploads are limited to 100 MB and conversion has a 120-second timeout.
