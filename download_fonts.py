import os
import urllib.request

FONTS = {
    "Overpass-Regular.ttf": "https://github.com/googlefonts/overpass/raw/master/fonts/ttf/Overpass-Regular.ttf",
    "Overpass-Medium.ttf": "https://github.com/googlefonts/overpass/raw/master/fonts/ttf/Overpass-Medium.ttf",
    "Overpass-SemiBold.ttf": "https://github.com/googlefonts/overpass/raw/master/fonts/ttf/Overpass-SemiBold.ttf",
    "Overpass-Bold.ttf": "https://github.com/googlefonts/overpass/raw/master/fonts/ttf/Overpass-Bold.ttf",
    "OverpassMono-Regular.ttf": "https://github.com/googlefonts/overpass/raw/master/fonts/ttf/OverpassMono-Regular.ttf",
    "OverpassMono-Medium.ttf": "https://github.com/googlefonts/overpass/raw/master/fonts/ttf/OverpassMono-Medium.ttf",
    "OverpassMono-SemiBold.ttf": "https://github.com/googlefonts/overpass/raw/master/fonts/ttf/OverpassMono-SemiBold.ttf",
}

os.makedirs("GUI/assets/fonts", exist_ok=True)

for name, url in FONTS.items():
    path = os.path.join("GUI/assets/fonts", name)
    if not os.path.exists(path):
        print(f"Downloading {name}...")
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as e:
            print(f"Failed to download {name}: {e}")
