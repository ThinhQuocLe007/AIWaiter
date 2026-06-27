# Empty package marker so `from scripts.X import Y` resolves to *our* scripts/ (a flat
# directory of standalone scripts) instead of Python's implicit namespace-package merge with
# /opt/ros/humble/.../scripts (a real package, also named "scripts", that ROS puts on PYTHONPATH
# when sourced via /opt/ros/humble/setup.bash). Without this, namespace-package merging means
# `from scripts.build_centroids import main` can resolve to a *different* scripts package and
# ImportError on a missing submodule.
