# How to release

* Make sure you're on main and synced to HEAD
* Ensure the project builds and tests run
    * `parallel -j0 exec ::: test/*_test` can help ensure everything at least
      passes
* Prepare release notes
    * `git log $(git describe --abbrev=0 --tags)..HEAD` gives you the list of
      commits between the last annotated tag and HEAD
    * Pick the most interesting.
* Create one last commit that updates the version saved in `CMakeLists.txt`, `MODULE.bazel`,
  and `bindings/python/google_benchmark/__init__.py` to the release version you're creating.
  (This version will be used if benchmark is installed from the archive you'll be creating
  in the next step.)

```
# CMakeLists.txt
project (benchmark VERSION 1.9.0 LANGUAGES CXX)
```

```
# MODULE.bazel
module(name = "com_github_google_benchmark", version="1.9.0")
```

```
# google_benchmark/__init__.py
__version__ = "1.9.0"
```

* Create a release through github's interface
    * Note this will create a lightweight tag.
    * Update this to an annotated tag:
      * `git pull --tags`
      * `git tag -a -f <tag> <tag>`
      * `git push --force --tags origin`
* Confirm that the "Build and upload Python wheels" action runs to completion
    * Run it manually if it hasn't run.
