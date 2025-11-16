#!/bin/bash
# Download Material Design 3 fonts for offline use

set -e

FONTS_DIR="app/static/fonts"
mkdir -p "$FONTS_DIR"

echo "Downloading Material Symbols Rounded font..."
# Material Symbols Rounded - variable font (direct URL)
curl -L "https://fonts.gstatic.com/s/materialsymbolsrounded/v156/syl0-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190FjpZIvDmUSVOK7BDB_Qb9vUSzq3wzLK-P0J-V_Zs-QtQth3-jOc7TOVpeRL2w5rwZu2rIekXxKJKJBj_ys.woff2" \
  -o "$FONTS_DIR/MaterialSymbolsRounded.woff2"

echo "Downloading Roboto font..."
# Roboto Regular 400
curl -L "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxK.woff2" \
  -o "$FONTS_DIR/Roboto-Regular.woff2"

# Roboto Medium 500
curl -L "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmEU9fBBc4.woff2" \
  -o "$FONTS_DIR/Roboto-Medium.woff2"

# Roboto Bold 700
curl -L "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmWUlfBBc4.woff2" \
  -o "$FONTS_DIR/Roboto-Bold.woff2"

echo "Downloading Roboto Mono font..."
# Roboto Mono Regular 400
curl -L "https://fonts.gstatic.com/s/robotomono/v23/L0xuDF4xlVMF-BfR8bXMIhJHg45mwgGEFl0_3vq_ROW4.woff2" \
  -o "$FONTS_DIR/RobotoMono-Regular.woff2"

# Roboto Mono Medium 500
curl -L "https://fonts.gstatic.com/s/robotomono/v23/L0xuDF4xlVMF-BfR8bXMIhJHg45mwgGEFl0_gPq_ROW4.woff2" \
  -o "$FONTS_DIR/RobotoMono-Medium.woff2"

echo "Creating local font CSS..."
cat > "$FONTS_DIR/fonts.css" << 'EOF'
/* Material Symbols Rounded - Variable Font */
@font-face {
  font-family: 'Material Symbols Rounded';
  font-style: normal;
  font-weight: 100 700;
  src: url('/static/fonts/MaterialSymbolsRounded.woff2') format('woff2');
  font-display: swap;
}

/* Roboto Regular */
@font-face {
  font-family: 'Roboto';
  font-style: normal;
  font-weight: 400;
  src: url('/static/fonts/Roboto-Regular.woff2') format('woff2');
  font-display: swap;
}

/* Roboto Medium */
@font-face {
  font-family: 'Roboto';
  font-style: normal;
  font-weight: 500;
  src: url('/static/fonts/Roboto-Medium.woff2') format('woff2');
  font-display: swap;
}

/* Roboto Bold */
@font-face {
  font-family: 'Roboto';
  font-style: normal;
  font-weight: 700;
  src: url('/static/fonts/Roboto-Bold.woff2') format('woff2');
  font-display: swap;
}

/* Roboto Mono Regular */
@font-face {
  font-family: 'Roboto Mono';
  font-style: normal;
  font-weight: 400;
  src: url('/static/fonts/RobotoMono-Regular.woff2') format('woff2');
  font-display: swap;
}

/* Roboto Mono Medium */
@font-face {
  font-family: 'Roboto Mono';
  font-style: normal;
  font-weight: 500;
  src: url('/static/fonts/RobotoMono-Medium.woff2') format('woff2');
  font-display: swap;
}
EOF

echo "Fonts downloaded successfully to $FONTS_DIR"
ls -lh "$FONTS_DIR"
