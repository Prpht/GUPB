import numpy as np
from sklearn.preprocessing import OneHotEncoder
from tensorflow.keras import backend as K
from tensorflow.keras.layers import Conv2D, Input, Flatten, Dense, Lambda, Add
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import RMSprop, Adam

weapon_encoder = OneHotEncoder(sparse=False, handle_unknown='ignore')
weapon_encoder.fit(np.array([["amulet"], ["axe"], ["bow"], ["knife"], ["sword"]]))

facing_encoder = OneHotEncoder(sparse=False, handle_unknown='ignore')
facing_encoder.fit(np.array([["UP"], ["RIGHT"], ["DOWN"], ["LEFT"]]))


def build_model(input_shape, action_space, dueling):
    X_input = Input(input_shape)
    X = X_input

    X = Conv2D(128, kernel_size=(3, 3), strides=(1, 1), padding="valid", input_shape=input_shape, activation="relu", data_format="channels_last")(X)
    X = Conv2D(64, kernel_size=(3, 3), strides=(1, 1), padding="valid", activation="relu", data_format="channels_last")(X)
    X = Conv2D(64, kernel_size=(3, 3), strides=(1, 1), padding="valid", activation="relu", data_format="channels_last")(X)
    X = Flatten()(X)
    # 'Dense' is the basic form of a neural network layer
    X = Dense(512, activation="relu", kernel_initializer='he_uniform')(X)

    # Hidden layer with 256 nodes
    X = Dense(256, activation="relu", kernel_initializer='he_uniform')(X)

    # Hidden layer with 64 nodes
    X = Dense(64, activation="relu", kernel_initializer='he_uniform')(X)

    if dueling:
        state_value = Dense(1, kernel_initializer='he_uniform')(X)
        state_value = Lambda(lambda s: K.expand_dims(s[:, 0], -1), output_shape=(action_space,))(state_value)

        action_advantage = Dense(action_space, kernel_initializer='he_uniform')(X)
        action_advantage = Lambda(lambda a: a[:, :] - K.mean(a[:, :], keepdims=True), output_shape=(action_space,))(action_advantage)

        X = Add()([state_value, action_advantage])
    else:
        X = Dense(action_space, activation="linear", kernel_initializer='he_uniform')(X)

    model = Model(inputs=X_input, outputs=X)
    model.compile(loss="mean_squared_error", optimizer=Adam(lr=0.00025), metrics=["accuracy"])
    # model.compile(loss="mean_squared_error", optimizer=RMSprop(lr=0.00025, rho=0.95, epsilon=0.01), metrics=["accuracy"])

    model.summary()
    return model
