"""AI（gpt-4o-mini）で生成した初期問題バンク（教員が管理画面から編集・追加できる）。

Versant等の商用テストの問題を複製したものではなく、独自に生成したオリジナル問題。
.gitignore の `*.json` 除外ルールに引っかからないよう、Pythonリテラルとして保持する
（debate/config.py の DEFAULT_MOTIONS と同じ方式）。
"""

SEED_QUESTIONS: dict[str, list[dict]] = {
  "repeat": [
    {
      "text": "I enjoy reading books every evening.",
      "level": "A2"
    },
    {
      "text": "The weather is nice today, isn't it?",
      "level": "A2"
    },
    {
      "text": "My favorite subject in school is mathematics.",
      "level": "A2"
    },
    {
      "text": "She is going to the store to buy some milk.",
      "level": "A2"
    },
    {
      "text": "There was a big event in the city last weekend.",
      "level": "A2"
    },
    {
      "text": "I usually have breakfast at 7 o'clock.",
      "level": "A2"
    },
    {
      "text": "Do you like to play video games with friends?",
      "level": "A2"
    },
    {
      "text": "He studies hard for his exams every year.",
      "level": "A2"
    },
    {
      "text": "I watched a movie about space exploration yesterday.",
      "level": "B1"
    },
    {
      "text": "Many students participated in the science fair last week.",
      "level": "B1"
    },
    {
      "text": "There are many interesting places to visit in Japan.",
      "level": "B1"
    },
    {
      "text": "I think learning English is very important for everyone.",
      "level": "B1"
    }
  ],
  "sentence_build": [
    {
      "target_sentence": "I like to eat sushi on weekends.",
      "level": "A2"
    },
    {
      "target_sentence": "My brother plays soccer every Saturday.",
      "level": "A2"
    },
    {
      "target_sentence": "She often goes to the library after school.",
      "level": "A2"
    },
    {
      "target_sentence": "They are studying for their final exams now.",
      "level": "A2"
    },
    {
      "target_sentence": "He will visit his grandparents next month.",
      "level": "A2"
    },
    {
      "target_sentence": "I want to travel to Europe next summer.",
      "level": "B1"
    },
    {
      "target_sentence": "My favorite hobby is painting landscapes.",
      "level": "B1"
    },
    {
      "target_sentence": "We should help each other with homework.",
      "level": "B1"
    },
    {
      "target_sentence": "She enjoys listening to music while studying.",
      "level": "B1"
    },
    {
      "target_sentence": "They have decided to join a cooking class together.",
      "level": "B1"
    },
    {
      "target_sentence": "I believe that exercise is important for health.",
      "level": "B2"
    },
    {
      "target_sentence": "Learning new languages can open many doors.",
      "level": "B2"
    }
  ],
  "qa": [
    {
      "question": "What is your favorite food and why?",
      "level": "A2"
    },
    {
      "question": "How do you usually spend your weekends?",
      "level": "A2"
    },
    {
      "question": "What sport do you like to play or watch?",
      "level": "A2"
    },
    {
      "question": "Who is your best friend and what do you like to do together?",
      "level": "A2"
    },
    {
      "question": "What kind of music do you enjoy listening to?",
      "level": "A2"
    },
    {
      "question": "Why do you think learning English is important?",
      "level": "B1"
    },
    {
      "question": "Describe a memorable trip you have taken.",
      "level": "B1"
    },
    {
      "question": "What do you like to do in your free time?",
      "level": "B1"
    },
    {
      "question": "If you could visit any country, which one would you choose?",
      "level": "B1"
    },
    {
      "question": "What is one skill you would like to learn in the future?",
      "level": "B1"
    },
    {
      "question": "How do you think technology has changed our lives?",
      "level": "B2"
    },
    {
      "question": "What are your thoughts on the importance of environmental protection?",
      "level": "B2"
    }
  ]
}
