# Get version from git describe
GIT_VERSION=$(git describe)

# Format the version to be PEP440 compliant
PEP440_VERSION=$(echo $GIT_VERSION | sed -e "s/^v//" -e "s/-/\.dev/" -e "s/-g/+/")

# Update and build with poetry
poetry version $PEP440_VERSION

# Stage and amend commit
git add pyproject.toml
git commit --amend --no-edit

# Build project
BUILD_OUTPUT=$(poetry build)

# Check if upload URL was passed as an argument
if [ $# -eq 1 ]; then
    # Extract the name of the .whl file
  WHL_FILE=$(echo "${BUILD_OUTPUT}" | grep -oP 'Built.*\.whl' | awk '{print $2}')

    # Construct the full path to the .whl file
    WHL_FILE_PATH="${PWD}/dist/${WHL_FILE}"

    echo $WHL_FILE_PATH

    # Upload
    curl -F expiration=1hour -F file=@${WHL_FILE_PATH} -X POST -w '%{redirect_url}\n' $1
else
    echo "Upload URL not specified, skipping upload"
fi
