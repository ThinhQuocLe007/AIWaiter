#!/bin/bash
# setup_env.sh — Source ROS2 Humble + build/source colcon by PROFILE.
#
#   source setup_env.sh sim    # PC demo:    sim    (gazebo/ignition)
#   source setup_env.sh real   # Jetson:     real   (real robot, light)
#   source setup_env.sh        # default = sim
#
# Why profiles: sim and real are DIFFERENT robots (only the logic is alike),
# so the two trees are fully independent — there is no shared "common".
#   - sim/  (TurtleBot4 description/msgs/nav/viz/node + worlds, ignition_bringup,
#            food_delivery) is only needed on the PC.
#   - real/ (ai_hw_bridge, drivers) is only needed on the Jetson Orin Nano.
# => colcon --base-paths builds just the right folder, so the Jetson never
#    touches the heavy simulation packages.

PROFILE="${1:-sim}"
WS_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV_NAME=".venv"

case "$PROFILE" in
  sim)  BASE_PATHS=("$WS_PATH/src/sim")  ;;
  real) BASE_PATHS=("$WS_PATH/src/real") ;;
  *) echo "[!] Invalid profile: '$PROFILE' (use: sim | real)"; return 1 ;;
esac

echo "-------------------------------------------------------"
echo "AI Waiter ROS2 workspace  |  PROFILE = $PROFILE"
echo "-------------------------------------------------------"

# 1) Global ROS2 Humble
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
    echo "[1/4] ROS2 Humble sourced."
else
    echo "[!] Error: ROS2 Humble not found at /opt/ros/humble/"
    return 1
fi

# 2) Python venv (--system-site-packages so it can see the system rclpy/tf2).
#    Switch to 'uv venv --python /usr/bin/python3.10 --system-site-packages' if you prefer uv pip.
if [ -d "$WS_PATH/$VENV_NAME" ]; then
    source "$WS_PATH/$VENV_NAME/bin/activate"
    echo "[2/4] venv '$VENV_NAME' activated."
else
    echo "[!] '$VENV_NAME' not found — creating one with --system-site-packages..."
    # Prefer stdlib venv; fall back to uv if python3-venv (ensurepip) is missing.
    if ! python3 -m venv --system-site-packages "$WS_PATH/$VENV_NAME" 2>/dev/null; then
        echo "[!] python3 -m venv failed (python3-venv not installed?) — trying uv..."
        rm -rf "$WS_PATH/$VENV_NAME"
        if command -v uv >/dev/null 2>&1; then
            uv venv --python /usr/bin/python3.10 --system-site-packages "$WS_PATH/$VENV_NAME"
        else
            echo "[!] Neither python3-venv nor uv is available. Install one of:"
            echo "      sudo apt install python3.10-venv     # stdlib venv"
            echo "      pipx install uv  (or: pip install uv) # uv"
            return 1
        fi
    fi
    if [ -f "$WS_PATH/$VENV_NAME/bin/activate" ]; then
        source "$WS_PATH/$VENV_NAME/bin/activate"
        echo "[2/4] venv '$VENV_NAME' created and activated."
    else
        echo "[!] venv creation failed — see messages above."
        return 1
    fi
fi

# 3) colcon build ONLY the folders for this profile
echo "[3/4] colcon build --base-paths ${BASE_PATHS[*]#$WS_PATH/}"
( cd "$WS_PATH" && colcon build --symlink-install --base-paths "${BASE_PATHS[@]}" )

# 4) Source the overlay
if [ -f "$WS_PATH/install/setup.bash" ]; then
    source "$WS_PATH/install/setup.bash"
    echo "[4/4] Workspace overlay sourced."
else
    echo "[!] install/setup.bash not found — check the build log."
fi

echo "-------------------------------------------------------"
echo "Done ($PROFILE). In every new terminal: source setup_env.sh $PROFILE"
echo "-------------------------------------------------------"
