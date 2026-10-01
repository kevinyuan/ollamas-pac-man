# Reproducing Ollama's Pac-Man decision-model demo

*The model itself was fast. Describing the game to it took most of the work, and adding one missing fact raised the mean score from 587 to 1,020.*

![The replay page: the board, the request sent to the model, and its response, side by side](https://raw.githubusercontent.com/kevinyuan/ollamas-pac-man/main/docs/img/replay.png)

Ollama's post [*Ollama now supports Jev-style decision models*](https://ollama.com/blog/ollama-now-supports-jev-style-decision-models) includes a small Pac-Man game that a local model plays one decision at a time, at 91 ms per decision. The post shows the game and the model's answers but not the request behind each answer, so I could not tell what the model was actually being asked. I rebuilt the game to find out how much that request matters. This is an independent reproduction and is not affiliated with Ollama. The code is at [kevinyuan/ollamas-pac-man](https://github.com/kevinyuan/ollamas-pac-man).

## What the demo asks of the model

The new `/v1/systemone` endpoint takes a `state` (text) and a set of named questions, and returns one answer per question. In the Pac-Man demo each move is a single `choice` question over the legal directions. The answer contains the chosen option, a probability for every option, and a confidence value, and the game receives nothing else from the model.

That leaves two strings to design: what goes into `state`, and what is written beside each option. Below is one of the requests I settled on, followed by the answer it received in a recorded run.

```json
{
  "state": { "game": "Pac-Man" },
  "questions": { "move": {
    "type": "choice",
    "instructions": "Each option describes what you would find by moving that way. Pick the move that heads toward a dot, and never toward a close ghost or a ghost in a side passage. Which move do you pick?",
    "criteria": {
      "up":   "Moving up: there is a dot ahead, no ghost is in sight, and the side passages are clear.",
      "down": "Moving down: there is a dot ahead, no ghost is in sight, and the side passages are clear."
    }
  } }
}
```

```json
{ "answers": { "move": { "choice": "up", "probabilities": { "up": 0.53, "down": 0.47 }, "confidence": 0.00 } } }
```

Both options read the same here, and the probabilities came out at 0.53 and 0.47. With nothing to separate the options, the model has no basis for a preference, so whatever distinguishes them has to be in the option text.

## What I built

The project has a small Pac-Man engine in Python, a JavaScript port that follows the same rules, and a breadth-first-search (BFS) player as a reference. A browser page has three tabs: Replay shows recorded runs with each request next to its response, You play lets you play it yourself, and Model plays drives the game with your own Ollama endpoint. The page is plain HTML and JavaScript, so nothing needs to be deployed. Every request is logged, and a finished game can be replayed deterministically, which let me work out why each life was lost.

I used `nimble`, the 9B decision model named in the post, through Ollama 0.35 on a MacBook Air. A decision takes about 1.2 s there instead of 91 ms. The post's figure comes from different hardware, and I cannot separate the hardware from anything else. The difference does not affect the results below, because the game is turn-based: the ghosts wait for the model, so a slow answer cannot cost a life.

Scoring is +10 per dot and −50 per catch, with three lives. The game in the post comes to about 1,180 under these rules (133 of 150 dots and three catches). Its ghosts move differently from mine, so I treat that number as context and not as a target.

## Experiment 1: the board as text

The most direct input is the maze itself, one character per cell, with a legend. With this input the model scored −80 in all three games. It ate 7 dots and then lost all three lives while moving left and right as the ghosts approached. Explaining how to read the grid (rows, directions, the goal) raised agreement with the BFS player slightly in an offline check on 60 positions, but it stayed close to chance, and raw coordinates did not do much better.

A set of small controlled tasks showed where the difficulty lies. When the model is given one target in plain words ("the dot is 3 right and 2 up"), it picks the right direction 90 to 100% of the time. When it is given six dots and asked for the nearest, accuracy falls to 36–40% against a chance level of 32%, and listing the nearest dot first did not help. The model can use a fact that is stated to it, but it cannot pick one out of a list.

## Experiment 2: precomputed facts, and what they leak

I then moved the computation into the options by using BFS to write labels such as "nearest dot 6 steps" and `DEADLY: ghost adjacent`. These looked very good offline, with 80% agreement with the BFS player and almost no steps next to a ghost.

To see how much of that came from the model, I wrote a rule with no model that reads the same labels: skip any `DEADLY` option, then take the smallest distance. Over 20 games the rule averaged 1,285 points against 1,384 for the BFS player, so the labels already contained the answer. The model, given the same labels, averaged 713 over three games. From then on I compared every variant with a plain rule that sees the same facts, because otherwise a good result could simply reflect a prompt that gives the answer away. The remaining experiments use facts that can be read directly off the board, such as what is straight ahead and what is beside the next cell, without any search.

## Experiment 3: the same facts, written differently

With the facts fixed, I changed only the wording. Agreement with the BFS player on the same 60 positions was:

- word fragments such as `dot, no ghost`: 65%
- full sentences such as `Moving left: there is a dot ahead, and no ghost is in sight.`: 80%
- full sentences with an instruction that ends in a question: 83%

The sentences added no information; they simply read better to the model. Ending the instruction with a real question ("Which move do you pick?") helped slightly, within the noise of this sample. Rewriting the instruction as an evaluation ("moving toward a ghost is bad") lowered agreement, so the content of the instruction mattered more than its final punctuation.

Per-position agreement also turned out to predict whole games poorly: two variants with the same 83% scored 587 and 1,020 points over full games. After that I judged variants on whole games.

## Experiment 4: reading the failures

I replayed every lost game and asked, for each lost life, whether a safe move had existed. A loss can be unavoidable, when every option was next to a ghost. It can be a blind spot, when the prompt showed no danger although there was one. It can also be a model error, when the prompt showed the danger and the model chose it anyway.

All nine lost lives in the raw-grid runs were model errors. In the sentence version with a straight-line view, six of nine were blind spots: a ghost waiting in a side passage next to the cell the model moved into, which a straight-line view cannot show. The model had read its prompt correctly, and the prompt lacked the information. I added one fact to each option, namely whether a ghost is in a side passage next to that cell.

Mean score over three games, by what the model is told:

- the whole board as characters: −80
- word fragments, straight-line view: 553
- sentences, straight-line view: 587
- sentences plus the side-passage fact: 1,020
- the same plus "this move heads toward the nearest dot": 937
- BFS-computed labels, which leak the answer: 713
- for reference, with no model: random 63, a rule on the sentence facts 1,172, the BFS player 1,384 (20 games each)

Blind-spot losses dropped from six to zero, so the gain came from supplying the missing fact, and no rewording produced it.

## What remains

With the information complete, every remaining avoidable loss was the model's own choice. In the three games with the side-passage fact (without the nearest-dot hint), the model moved into a ghost it had been warned about six times, and in each case the same option also said that a dot lay ahead, so the dot seems to outweigh the warning. When a dangerous option was marked with an explicit `DEADLY` and mentioned no dot, the model never walked into it (0 of 228 opportunities), compared with 6 of 308 in the sentence version, where the warning could sit beside a dot. That label version also contained the BFS leak, so I read this as a lead and not as proof. The next experiment tests it directly: describe the dangerous option plainly and leave the dot out.

## Takeaways

1. The model uses a stated fact well and finds a fact in a list badly, so the facts belong in the option text, written as sentences.
2. Selecting the nearest of several candidates failed, so that step is better computed outside the model.
3. A plain rule on the same facts is the baseline that shows whether the model or the prompt is responsible for a result. Here the rule matches or beats the model, so this is a study of how to describe a situation to a decision model. It does not show that a model plays Pac-Man better than a few lines of code.
4. Whole-game results and a classification of each lost life were more informative than per-position agreement, which hid a twofold difference.
5. A missing fact can look like a model failure, so it is worth checking that the information was present before blaming the model.

## Limits

Each model variant has three games (the rules have 20 or more), with one model, one maze, and ghost behavior I wrote myself. Since I tried only a few wordings, every number is a lower bound on what a better prompt could achieve. I also do not know what request the demo in the post used, so none of this describes how Ollama built it.

## Try it

Everything runs in the browser. Clone [the repository](https://github.com/kevinyuan/ollamas-pac-man) (MIT), serve the `web/` folder, and open the Model plays tab to drive the game with your own endpoint, or open the Replay tab to read the requests. You need `ollama pull nimble`, and `OLLAMA_ORIGINS` must be set for any page that is not served from `localhost`; the page explains how. If you find a wording that does better than mine, I would like to see it.

*Thanks to Ollama for the post this reproduces. This is an unaffiliated project, and Pac-Man is a trademark of Bandai Namco Entertainment.*
