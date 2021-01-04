import tensorflow as tf
from gupb.model.characters import Action, ChampionKnowledge
from tf_agents.agents.categorical_dqn import categorical_dqn_agent
from tf_agents.environments import suite_gym
from tf_agents.networks import categorical_q_network
from tf_agents.utils import common
from tf_agents.replay_buffers import tf_uniform_replay_buffer

N_DISCRETE_ACTIONS = len(Action)

ARENA_NAMES = ['archipelago', 'dungeon', 'fisher_island', 'wasteland', 'island', 'mini']

SIZE = 7
num_iterations = 15000
min_q_value = -20
max_q_value = 20
n_step_update = 2
learning_rate = 1e-3
gamma = 0.99
log_interval = 200
eval_interval = 1000
num_eval_episodes = 10

###
### Training routines taken from https://www.tensorflow.org/agents/tutorials/9_c51_tutorial
###


def compute_avg_return(environment, policy, num_episodes=10):

    total_return = 0.0
    for _ in range(num_episodes):
        time_step = environment.reset()
        episode_return = 0.0

    while not time_step.is_last():
      action_step = policy.action(time_step)
      time_step = environment.step(action_step.action)
      episode_return += time_step.reward
    total_return += episode_return

    avg_return = total_return / num_episodes
    return avg_return.numpy()[0]


def run_training(env):
    train_env = suite_gym.wrap_env(env)

    categorical_q_net = categorical_q_network.CategoricalQNetwork(
        train_env.observation_spec(),
        train_env.action_spec())

    optimizer = tf.compat.v1.train.AdamOptimizer(learning_rate=learning_rate)

    train_step_counter = tf.compat.v2.Variable(0)

    agent = categorical_dqn_agent.CategoricalDqnAgent(
        train_env.time_step_spec(),
        train_env.action_spec(),
        categorical_q_network=categorical_q_net,
        optimizer=optimizer,
        min_q_value=min_q_value,
        max_q_value=max_q_value,
        n_step_update=n_step_update,
        td_errors_loss_fn=common.element_wise_squared_loss,
        gamma=gamma,
        train_step_counter=train_step_counter)

    replay_buffer = tf_uniform_replay_buffer.TFUniformReplayBuffer(
        data_spec=agent.collect_data_spec,
        batch_size=train_env.batch_size)

    agent.initialize()

    # (Optional) Optimize by wrapping some of the code in a graph using TF function.
    agent.train = common.function(agent.train)

    # Reset the train step
    agent.train_step_counter.assign(0)

    # Evaluate the agent's policy once before training.
    avg_return = compute_avg_return(train_env, agent.policy, num_eval_episodes)
    returns = [avg_return]

    dataset = replay_buffer.as_dataset(
        num_parallel_calls=3, num_steps=n_step_update + 1).prefetch(3)

    iterator = iter(dataset)

    for _ in range(num_iterations):

        # Sample a batch of data from the buffer and update the agent's network.
        experience, unused_info = next(iterator)
        train_loss = agent.train(experience)

        step = agent.train_step_counter.numpy()

        if step % log_interval == 0:
            print('step = {0}: loss = {1}'.format(step, train_loss.loss))

        if step % eval_interval == 0:
            avg_return = compute_avg_return(train_env, agent.policy, num_eval_episodes)
            print('step = {0}: Average Return = {1:.2f}'.format(step, avg_return))
            returns.append(avg_return)
