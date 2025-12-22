# Build project
BUILD_OUTPUT=$(uv build)

# Check if upload URL was passed as an argument
if [ $# -eq 1 ]; then
    # Extract the name of the .whl file
    WHL_FILE=$(echo "${BUILD_OUTPUT}" | grep -oP 'Successfully built.*\.whl' | awk '{print $2}')

    # Construct the full path to the .whl file
    WHL_FILE_PATH="${PWD}/dist/${WHL_FILE}"

    echo $WHL_FILE_PATH

    # Upload
    curl -F expiration=1hour -F file=@${WHL_FILE_PATH} -X POST -w '%{redirect_url}\n' $1
else
    echo "Upload URL not specified, skipping upload"
fi
