from transformers import pipeline

pipe = pipeline(
    "automatic-speech-recognition",
    model="vinai/PhoWhisper-large",
    device="mps"  # или "cpu"
)

result = pipe("test.wav")
print(result["text"])