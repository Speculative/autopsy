# Arch Linux Setup for Playwright

Since you're on Arch Linux, Playwright's automated dependency installation (`--with-deps`) won't work because it's designed for Ubuntu/Debian. Here's how to set up Playwright on Arch:

## Quick Start (Recommended)

The Chromium browser Playwright downloads is mostly self-contained. Just install the browsers without system deps:

```bash
npm run install:browsers
```

Then test that it works:

```bash
npm run test:scenarios
npm run test:e2e
```

**If you get errors about missing libraries**, install them using Option 2 below.

## Option 2: Install System Dependencies

If you encounter missing library errors, install the required system libraries via pacman:

```bash
sudo pacman -S --needed \
  nss \
  nspr \
  at-spi2-core \
  cups \
  libdrm \
  dbus \
  libxcb \
  libxkbcommon \
  libx11 \
  libxcomposite \
  libxdamage \
  libxext \
  libxfixes \
  libxrandr \
  mesa \
  pango \
  cairo \
  alsa-lib
```

Then try running the tests again:

```bash
npm run test:e2e
```

## What You Might Be Missing Without Full Dependencies

Without all system libraries, you might encounter issues with:
- Video recording of test runs (requires ffmpeg)
- Some font rendering edge cases
- Certain audio/video codecs

For testing the Autopsy HTML UI, none of these are critical - the tests will work fine.

## Troubleshooting

If you see errors like:
```
error while loading shared libraries: libnss3.so
```

Install the specific missing package:
```bash
sudo pacman -S nss
```

Then retry the tests.
