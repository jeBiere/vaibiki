from .internal import InternalAudioProcessor
from .glava import GlavaAudioProcessor


def create_audio_processor(config):
    audio_conf = config.get("audio", {})
    backend = audio_conf.get("backend", "internal")
    params = dict(audio_conf)
    params.pop("backend", None)
    if backend == "glava":
        return GlavaAudioProcessor(**params)
    return InternalAudioProcessor(**params)
