# GitHub-safe bundle

This export excludes files that GitHub would reject on a normal public repository, including the 1 GB raw dataset and the 343 MB model weights file.

The app still runs in a fallback mode using heuristic image recovery when the full checkpoint weights are not present.
