import os
from getpass import getpass
import numpy as np
from typing import List
import time
import statistics

import pandas as pd
import numpy as np
import openai
from sklearn.utils import shuffle

import numpy as np
from typing import List
import time
import statistics

import numpy as np

from guardrails import Guard
from guardrails.llm_providers import PromptCallableException
import openai

from main import JailbreakEmbeddings, _embed_function


JAILBREAK_DATASET_FILEPATH = "/Users/juliagomes/validator-template/validator/jailbreak_prompts_2023_05_07.csv"
VANILLA_PROMPTS_DATASET_FILEPATH = "/Users/juliagomes/validator-template/validator/regular_prompts_2023_05_07.csv"
NUM_FEW_SHOT_EXAMPLES = 10
MODEL = "gpt-3.5-turbo"
OUTFILE = f"{MODEL}_baseline_output.txt"
np.random.seed(838)

def evaluate_embeddings_guard_on_dataset(test_prompts: List[str], guard: Guard, train_prompts, embed_function):
    latency_measurements = []
    num_passed_guard = 0
    num_failed_guard = 0
    for prompt in test_prompts:
        try:
            start_time = time.perf_counter()
            response = guard(
                llm_api=openai.chat.completions.create,
                prompt=prompt,
                model="gpt-3.5-turbo",
                max_tokens=1024,
                temperature=0.5,
                metadata={
                    "embed_function": embed_function,
                    "user_input": prompt,
                    "sources": train_prompts,
                }
            )
            latency_measurements.append(time.perf_counter() - start_time)
            if response.validation_passed:
                num_passed_guard += 1
            else:
                num_failed_guard += 1
            total = num_passed_guard + num_failed_guard
            with open(OUTFILE, "a") as f:
                f.write(f"\nprompt:\n{prompt}")
                f.write(f"\nresponse:\n{response}")
                f.write(f"\n{100 * num_failed_guard / total:.2f}% of {total} prompts failed the JailbreakEmbeddings guard.")
                f.write(f"\n{100 * num_passed_guard / total:.2f}% of {total} prompts passed the JailbreakEmbeddings guard.")
        except PromptCallableException as e:
            # Dataset contains a few bad apples that result in a Open AI error for invalid inputs
            f.write(f"\nexception:\n{e}")
            pass
    return num_passed_guard, num_failed_guard, latency_measurements


def benchmark_arize_jailbreak_embeddings_validator(train_prompts, jailbreak_test_prompts, vanilla_prompts):
    guard = Guard.from_string(
        validators=[
            JailbreakEmbeddings(threshold=0.2, validation_method="full", on_fail="refrain", sources=train_prompts)
        ],
    )
    num_passed_guard, num_failed_guard, latency_measurements = evaluate_embeddings_guard_on_dataset(
        test_prompts=jailbreak_test_prompts,
        guard=guard, train_prompts=train_prompts, embed_function=_embed_function)
    with open(OUTFILE, "a") as f:
        f.write(f"\n{num_passed_guard} True Positives")
        f.write(f"\n{num_failed_guard} False Negatives")
        f.write(f"\n{statistics.median(latency_measurements)} median latency\n{statistics.mean(latency_measurements)} mean latency\n{max(latency_measurements)} max latency")

    num_passed_guard, num_failed_guard, latency_measurements = evaluate_embeddings_guard_on_dataset(
        test_prompts=vanilla_prompts,
        guard=guard, train_prompts=train_prompts, embed_function=_embed_function)
    with open(OUTFILE, "a") as f:
        f.write(f"\n{num_failed_guard} True Negatives")
        f.write(f"\n{num_passed_guard} False Positives")
        f.write(f"\n{statistics.median(latency_measurements)} median latency\n{statistics.mean(latency_measurements)} mean latency\n{max(latency_measurements)} max latency")


def get_prompts(filename: str) -> List[str]:
    script_dir = os.path.dirname(__file__)  # Get the directory where the script is located
    # Dataset from public repo associated with arxiv paper https://github.com/verazuo/jailbreak_llms
    file_path = os.path.join(script_dir, filename)
    prompts = shuffle(pd.read_csv(file_path))["prompt"].tolist()
    return prompts


def main():
    # Jailbreak prompts that we expect to Fail the Guard
    jailbreak_prompts = get_prompts("jailbreak_prompts_2023_05_07.csv")
    train_prompts = jailbreak_prompts[-NUM_FEW_SHOT_EXAMPLES:]
    test_prompts = jailbreak_prompts[:-NUM_FEW_SHOT_EXAMPLES]

    # Vanilla prompts that we expect to Pass the Guard
    vanilla_prompts = get_prompts("regular_prompts_2023_05_07.csv")

    benchmark_arize_jailbreak_embeddings_validator(jailbreak_test_prompts=test_prompts, vanilla_prompts=vanilla_prompts, train_prompts=train_prompts)


if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = getpass("🔑 Enter your OpenAI API key: ")
    main()