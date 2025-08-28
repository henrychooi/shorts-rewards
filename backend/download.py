from huggingface_hub import snapshot_download

# This will download the entire repository to a local cache
# The default cache location is ~/.cache/huggingface/hub
# You can specify a different path with `local_dir`
snapshot_download(repo_id="openai/whisper-medium.en")

print("Model has been downloaded locally.")