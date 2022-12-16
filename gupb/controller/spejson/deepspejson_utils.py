import os
import tensorflow as tf

# Yup, you see it right. Globally shared singleton! I know, it's generally terrible Pythonic anti-pattern, but oh boy,
# you really don't want to reload and retrace it more often than once. Trust me, I know what I'm doing here.
model_predict = None


def load_model_and_make_servable():
    global model_predict
    if not model_predict:
        model = tf.keras.models.load_model(
            os.path.join('gupb', 'controller', 'spejson', 'deepspejson.h5'), compile=False)

        # This little 1-line fella is pretty much a game-changes. Like really! 3x performance improvement for free.
        @tf.function(reduce_retracing=True, jit_compile=True)
        def predict(X, h0, c0, mask):
            return model([X, h0, c0, mask])

        model_predict = predict

    return model_predict
