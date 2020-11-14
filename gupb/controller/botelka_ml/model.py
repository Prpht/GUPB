import random

import numpy as np

from gupb.model.characters import Action
import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()


class DeepLearning:
    def __init__(self):
        # TODO: needs to be equal to number of episodes * number of games
        iterations = 200 * 20

        self.learning_rate = 0.5
        self.discount = 0.95  # How much we appreciate future reward over current
        self.exploration_rate = 1.0  # Initial exploration rate
        self.exploration_delta = 1.0 / iterations  # Shift from exploration to exploration

        # 10 neurons for max 5 players
        self.input_count = 16

        # 5 actions possible (5 neurons)
        self.output_count = 5

        # Will ne initialized in define_model
        self.model_input = None
        self.model_output = None
        self.target_output = None
        self.optimizer = None
        self.initializer = None
        # ---

        self.session = tf.Session()
        self.define_model()
        self.session.run(self.initializer)

    def define_model(self):
        # Input is an array of single item (state). Input is 2-dimensional
        self.model_input = tf.placeholder(dtype=tf.float32, shape=[None, self.input_count])

        # 8 hidden neurons per layer
        # TODO: Experiment with different values
        layer_size = 8

        # Two hidden layers of 8 neurons with sigmoid activation initialized to zero for stability
        fc1 = tf.layers.dense(
            self.model_input,
            layer_size,
            activation=tf.sigmoid,
            kernel_initializer=tf.constant_initializer(np.zeros((self.input_count, layer_size)))
        )
        fc2 = tf.layers.dense(
            fc1,
            layer_size,
            activation=tf.sigmoid,
            kernel_initializer=tf.constant_initializer(np.zeros((layer_size, self.output_count)))
        )

        # Output has 5 values
        self.model_output = tf.layers.dense(fc2, self.output_count)

        # This is for feeding training output (a.k.a ideal target values)
        self.target_output = tf.placeholder(shape=[None, self.output_count], dtype=tf.float32)
        # Loss is mean squared difference between current output and ideal target values
        loss = tf.losses.mean_squared_error(self.target_output, self.model_output)
        # Optimizer adjusts weights to minimize loss, with the speed of learning_rate
        self.optimizer = tf.train.GradientDescentOptimizer(learning_rate=self.learning_rate).minimize(loss)
        # Initializer to set weights to initial values
        self.initializer = tf.global_variables_initializer()
        self.saver = tf.train.Saver()

        # !!!!!!!!!!!!!!!!!!!!!!!!!!!
        self.load()
        self.exploration_rate = 0
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!

    # Ask model to estimate Q value for specific state (inference)
    def get_q(self, state):
        # Model input: Single state represented by array of single item (state)
        # Model output: Array of Q values for single state
        return self.session.run(self.model_output, feed_dict={self.model_input: [state]})[0]  # TODO: [[state]]

    def get_next_action(self, state):
        if random.random() > self.exploration_rate:  # Explore (gamble) or exploit (greedy)
            return self.greedy_action(state)
        else:
            return self.random_action()

    # Which action (FORWARD or BACKWARD) has bigger Q-value, estimated by our model (inference).
    def greedy_action(self, state):
        MAPPING = {
             0: Action.DO_NOTHING, 1: Action.TURN_LEFT, 2: Action.TURN_RIGHT, 3: Action.STEP_FORWARD, 4: Action.ATTACK
        } 
        # argmax picks the higher Q-value and returns the index (FORWARD=0, BACKWARD=1)
        return MAPPING[np.argmax(self.get_q(state))]

    def random_action(self):
        actions = [
            Action.DO_NOTHING, Action.TURN_LEFT, Action.TURN_RIGHT, Action.STEP_FORWARD, Action.ATTACK
        ]
        random_action = random.choice(actions)
        return random_action

    def train(self, old_state, action, reward, new_state):
        # Ask the model for the Q values of the old state (inference)
        old_state_q_values = self.get_q(old_state)

        # Ask the model for the Q values of the new state (inference)
        new_state_q_values = self.get_q(new_state)

        MAPPING = {
             Action.DO_NOTHING: 0, Action.TURN_LEFT: 1, Action.TURN_RIGHT: 2, Action.STEP_FORWARD: 3, Action.ATTACK: 4
        } 
        # Real Q value for the action we took. This is what we will train towards.
        old_state_q_values[MAPPING[action]] = reward + self.discount * np.amax(new_state_q_values)

        # Setup training data
        training_input = [old_state]  # TODO: [[old_state]]

        target_output = [old_state_q_values]
        training_data = {self.model_input: training_input, self.target_output: target_output}

        # Train
        self.session.run(self.optimizer, feed_dict=training_data)

    def update(self, old_state, new_state, action, reward):
        # Train our model with new data
        self.train(old_state, action, reward, new_state)

        # Finally shift our exploration_rate toward zero (less gambling)
        if self.exploration_rate > 0:
            self.exploration_rate -= self.exploration_delta

    def save(self):
        self.saver.save(self.session, "./tmp/model.ckpt")

    def load(self):
        self.saver.restore(self.session, "./tmp/model.ckpt")

model = None


# Switching context might break the net, to be verified.
def get_model():
    global model

    if not model:
        model = DeepLearning()

    return model
