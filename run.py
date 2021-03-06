"""
Copyright (C) 2018 Shane Steinert-Threlkeld

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
"""
from __future__ import print_function
from collections import defaultdict
import argparse

import tensorflow as tf
import pandas as pd

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import verbs
import util
import data
from models import basic_ffnn

tf.logging.set_verbosity(tf.logging.INFO)


class EvalEarlyStopHook(tf.train.SessionRunHook):
    """Evaluates estimator during training and implements early stopping.
    Writes output of a trial as CSV file.
    See https://stackoverflow.com/questions/47137061/. """

    def __init__(self, estimator, eval_input, filename, num_steps=50, stop_loss=0.02):

        self._estimator = estimator
        self._input_fn = eval_input
        self._num_steps = num_steps
        self._stop_loss = stop_loss
        # store results of evaluations
        self._results = defaultdict(list)
        self._filename = filename

    def begin(self):

        self._global_step_tensor = tf.train.get_or_create_global_step()
        if self._global_step_tensor is None:
            raise ValueError("global_step needed for EvalEarlyStop")

    def before_run(self, run_context):

        requests = {"global_step": self._global_step_tensor}
        return tf.train.SessionRunArgs(requests)

    def after_run(self, run_context, run_values):

        global_step = run_values.results["global_step"]
        if (global_step - 1) % self._num_steps == 0:
            ev_results = self._estimator.evaluate(input_fn=self._input_fn)

            print("")
            for key, value in ev_results.items():
                self._results[key].append(value)
                print("{}: {}".format(key, value))

            # TODO: add running total accuracy or other complex stop condition?
            if ev_results["loss"] < self._stop_loss:
                run_context.request_stop()

    def end(self, session):
        # write results to csv
        util.dict_to_csv(self._results, self._filename)


def run_trial(params, trial_num, write_path="/tmp/tf/verbs"):

    print("\n------ TRIAL {} -----".format(trial_num))

    tf.reset_default_graph()

    write_dir = "{}/trial_{}".format(write_path, trial_num)
    csv_file = "{}/trial_{}.csv".format(write_path, trial_num)

    # BUILD MODEL
    run_config = tf.estimator.RunConfig(
        save_checkpoints_steps=params["eval_steps"],
        save_checkpoints_secs=None,
        save_summary_steps=params["eval_steps"],
    )

    # TODO: moar models?
    model = tf.estimator.Estimator(
        model_fn=basic_ffnn, params=params, model_dir=write_dir, config=run_config
    )

    # GENERATE DATA
    generator = data.DataGenerator(
        params["verbs"],
        params["num_worlds"],
        params["max_cells"],
        params["items_per_bin"],
        params["tries_per_bin"],
        params["test_bin_size"],
    )

    train_x, train_y = generator.get_training_data()
    test_x, test_y = generator.get_test_data()

    # input fn for training
    train_input_fn = tf.estimator.inputs.numpy_input_fn(
        x={params["input_feature"]: train_x},
        y=train_y,
        batch_size=params["batch_size"],
        num_epochs=params["num_epochs"],
        shuffle=True,
    )

    # input fn for evaluation
    eval_input_fn = tf.estimator.inputs.numpy_input_fn(
        x={params["input_feature"]: test_x},
        y=test_y,
        batch_size=len(test_x),
        shuffle=False,
    )

    if params["train"]:
        print("\n-- TRAINING --")
        # train and evaluate model together, using the Hook
        model.train(
            input_fn=train_input_fn,
            hooks=[
                EvalEarlyStopHook(
                    model,
                    eval_input_fn,
                    csv_file,
                    params["eval_steps"],
                    params["stop_loss"],
                )
            ],
        )

    if params["predict"]:
        print("\n-- PREDICTING --")
        predictions = pd.DataFrame(model.predict(input_fn=eval_input_fn))
        predictions["true_label"] = test_y
        predictions["correct"] = (
            predictions["class_ids"] == predictions["true_label"]
        ).astype(int)
        predictions["dox_in_p"] = predictions["dox_in_p"].astype(int)
        predictions.to_csv("{}/trial_{}_predictions.csv".format(write_path, trial_num))


# DEFINE AN EXPERIMENT
def run_experiment(params):
    for trial in range(params["num_trials"]):
        run_trial(params, trial, params["write_dir"])


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    # what to do arguments
    parser.add_argument("--no_train", dest="train", action="store_false")
    parser.add_argument("--train", dest="train", action="store_true")
    parser.set_defaults(train=True)
    parser.add_argument("--no_eval", dest="eval", action="store_false")
    parser.add_argument("--eval", dest="eval", action="store_true")
    parser.set_defaults(eval=True)
    parser.add_argument("--no_predict", dest="predict", action="store_false")
    parser.add_argument("--predict", dest="predict", action="store_true")
    parser.set_defaults(predict=False)
    # get experiment parameters
    parser.add_argument("--config", type=str)
    # get parser args as a dict
    args = vars(parser.parse_args())

    # TODO: factor out read config logic into util?
    with open(args["config"], "r") as config_file:
        args.update(load(config_file, Loader=Loader))

    args["write_dir"] = args["name"] + "/data"

    run_experiment(args)
