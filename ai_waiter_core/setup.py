from setuptools import setup, find_packages

package_name = 'ai_waiter_core'

# NOTE: This package was moved out of the ROS2 workspace (robot_ws) and is now a
# pure-Python "brain". ROS packaging (package.xml / resource / ament data_files)
# has been removed. Final packaging — console_scripts + consolidating deps into
# the root pyproject.toml so `uv sync` installs it — is handled in Phase 2.
setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(include=[package_name, package_name + '.*']),
    install_requires=[
        'python-dotenv',
        'numpy',
        'torch>=2.0',
        'torchaudio>=2.0',
        'pyaudio>=0.2.11',
        'faster-whisper>=1.0.0',
        'edge-tts',
        'sounddevice',
        'soundfile',
        'langchain-core',
        'langchain-community',
        'langchain-huggingface',
        'langchain-ollama',
        'faiss-cpu',
        'rank-bm25',
        'sentence-transformers',
        'pydantic>=2.0',
        'langgraph',
    ],
    zip_safe=True,
    description='Core LLM and Agent logic for AI Waiter (brain)',
    license='Apache-2.0',
)
