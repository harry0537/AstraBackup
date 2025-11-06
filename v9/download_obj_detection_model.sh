#!/bin/bash
# Download MobileNet-SSD model files for object detection
# Run this script if automatic download fails

MODEL_DIR="/tmp/vision_v9/models"
mkdir -p "$MODEL_DIR"

cd "$MODEL_DIR"

echo "Downloading MobileNet-SSD model files..."
echo ""

# Prototxt file
echo "Downloading prototxt..."
PROTOTXT_URLS=(
    "https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/MobileNetSSD_deploy.prototxt"
    "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/MobileNetSSD_deploy.prototxt"
)

for url in "${PROTOTXT_URLS[@]}"; do
    echo "  Trying: $url"
    if wget -q "$url" -O MobileNetSSD_deploy.prototxt; then
        if [ -s MobileNetSSD_deploy.prototxt ]; then
            echo "  ✓ Prototxt downloaded successfully"
            break
        fi
    fi
done

# Model weights - try multiple sources
echo ""
echo "Downloading model weights (this may take 1-2 minutes, ~23MB)..."
MODEL_URLS=(
    "https://github.com/opencv/opencv_extra/raw/master/testdata/dnn/MobileNetSSD_deploy.caffemodel"
    "https://drive.google.com/uc?export=download&id=0B3gersZ2cHIxRm5PMWR5ekN4SEU"
)

for url in "${MODEL_URLS[@]}"; do
    echo "  Trying: $url"
    if wget -q "$url" -O MobileNetSSD_deploy.caffemodel; then
        SIZE=$(stat -c%s MobileNetSSD_deploy.caffemodel 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 1000000 ]; then
            echo "  ✓ Model weights downloaded successfully ($(echo "scale=1; $SIZE/1024/1024" | bc)MB)"
            break
        fi
    fi
done

# Verify files
echo ""
if [ -f MobileNetSSD_deploy.prototxt ] && [ -f MobileNetSSD_deploy.caffemodel ]; then
    PROTOTXT_SIZE=$(stat -c%s MobileNetSSD_deploy.prototxt)
    MODEL_SIZE=$(stat -c%s MobileNetSSD_deploy.caffemodel)
    echo "✓ Files downloaded:"
    echo "  prototxt: $PROTOTXT_SIZE bytes"
    echo "  model: $(echo "scale=1; $MODEL_SIZE/1024/1024" | bc)MB"
    echo ""
    echo "✓ Model files ready! Restart Vision Server to use object detection."
else
    echo "✗ Failed to download model files"
    echo ""
    echo "Manual download instructions:"
    echo "1. Visit: https://github.com/opencv/opencv_extra/tree/master/testdata/dnn"
    echo "2. Download: MobileNetSSD_deploy.prototxt"
    echo "3. Download: MobileNetSSD_deploy.caffemodel"
    echo "4. Place both files in: $MODEL_DIR"
fi

