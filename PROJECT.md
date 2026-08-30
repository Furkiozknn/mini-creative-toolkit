# mini-creative-toolkit

**Hedef**: Ücretli/GPU gerektiren dış servislere bağımlı olmadan, deterministik görsel/video işlerini (arka plan silme, boyutlandırma, format çevirme, thumbnail, gif, kırpma) yerelde CPU üzerinde çalıştıran bir MCP sunucusu.

**Kapsam dışı**: Görsel/video *üretimi* (bunun için nvidia-nim-mcp zaten var, ücretsiz hosted API). GPU gerektiren hiçbir işlem (yerel diffusion/upscale modeli) — bu makinede dedike GPU yok.

**Araç/stack**: Python + `uv`, `rembg` (ONNX, CPU) arka plan silme için, `Pillow` resize/format için, sistemde zaten kurulu `ffmpeg` video işleri için. MCP framework nvidia-nim-mcp ile aynı (`mcp[cli]`, `MCPServer` sınıfı) — tutarlılık için.

**Bitti tanımı**: `uv sync` hatasız kurulur, `uv run toolkit.py` MCP sunucusunu stdio üzerinden ayağa kaldırır, en az bir araç (`remove_background` veya `video_thumbnail`) gerçek bir dosya ile uçtan uca test edilip çalıştığı doğrulanır.
