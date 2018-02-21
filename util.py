import pandas as pd

# TODO: merge repo with quantifier one; common core? util + hooks? even runner?


def read_trials_from_csv(path, trials):
    """Reads trial information from CSV files.
    It's assumed that the files are named path/trial_X.csv, for each
    X in the list trials.

    Args:
        path: path to CSV files with trial info
        trials: list of trial IDs

    Returns:
        a dictionary, with keys being each X in trial, and values being
        Pandas DataFrames, as generated by get_table
    """
    data = {}
    for trial in trials:
        data[trial] = pd.DataFrame.from_csv(
            '{}/trial_{}.csv'.format(path, trial))
    return data


def dict_to_csv(data, filename):
    """Writes a dictionary to a CSV file.
    The header of the CSV file will be the keys from the dictionary.
    Values in the dict are lists of equal length; each row of the CSV
    file contains the next item from each list.

    Args:
        data: the dictionary containing data
        filename: file to write to
    """
    frame = pd.DataFrame(data)
    frame.to_csv(filename)
