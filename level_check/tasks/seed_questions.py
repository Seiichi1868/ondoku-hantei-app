"""初期問題バンク（教員が管理画面から編集・追加できる）。

商用テストの問題を複製したものではなく、独自に作成したオリジナル問題。
.gitignore の `*.json` 除外ルールに引っかからないよう、Pythonリテラルとして保持する。
"""

SEED_QUESTIONS: dict[str, list[dict]] = {
    "A": [
        {"question": "What is your favorite food?", "expected_answer": "Any plausible food name or short preference.", "level": "A2"},
        {"question": "How do you usually go to school?", "expected_answer": "By train / bus / walk / bicycle, etc.", "level": "A2"},
        {"question": "What time do you usually wake up?", "expected_answer": "A time of day.", "level": "A2"},
        {"question": "Do you prefer tea or coffee?", "expected_answer": "Tea, coffee, or neither with a brief reason.", "level": "A2"},
        {"question": "Where do you live?", "expected_answer": "A city, town, or area name.", "level": "A2"},
        {"question": "What subject do you like best at school?", "expected_answer": "A school subject.", "level": "A2"},
        {"question": "How many people are in your family?", "expected_answer": "A number of people.", "level": "A2"},
        {"question": "What did you do last weekend?", "expected_answer": "A short past activity.", "level": "B1"},
        {"question": "Why do people learn English?", "expected_answer": "A reason such as study, work, or travel.", "level": "B1"},
        {"question": "What is one thing that makes you happy?", "expected_answer": "An activity, person, or experience.", "level": "B1"},
        {"question": "How often do you exercise?", "expected_answer": "A frequency expression.", "level": "B1"},
        {"question": "If it rains tomorrow, what will you do?", "expected_answer": "A conditional plan.", "level": "B1"},
    ],
    "B": [
        {"text": "I enjoy reading books every evening.", "level": "A2"},
        {"text": "The weather is nice today, isn't it?", "level": "A2"},
        {"text": "My favorite subject in school is science.", "level": "A2"},
        {"text": "She is going to the store to buy some milk.", "level": "A2"},
        {"text": "I usually have breakfast at seven o'clock.", "level": "A2"},
        {"text": "He studies hard for his exams every year.", "level": "A2"},
        {"text": "There are many interesting places to visit in Japan.", "level": "B1"},
        {"text": "I watched a movie about space exploration yesterday.", "level": "B1"},
        {"text": "Many students participated in the science fair last week.", "level": "B1"},
        {"text": "Learning a new language takes time and practice.", "level": "B1"},
        {"text": "She asked me if I could help her with her homework.", "level": "B1"},
        {"text": "Although it was raining, they decided to go hiking.", "level": "B2"},
    ],
    "C": [
        {
            "dialog_text": "A: Hi, Tom. Are you free this Saturday?\nB: Sorry, I have a soccer practice in the morning.\nA: How about Sunday afternoon?\nB: Sunday works for me.",
            "question": "When can Tom meet?",
            "expected_answer": "Sunday afternoon.",
            "level": "A2",
        },
        {
            "dialog_text": "A: Excuse me, where is the library?\nB: Go straight and turn left at the traffic light. It's next to the post office.\nA: Thank you!\nB: You're welcome.",
            "question": "What is next to the library?",
            "expected_answer": "The post office.",
            "level": "A2",
        },
        {
            "dialog_text": "A: Did you finish the history report?\nB: Not yet. I still need two more sources.\nA: The deadline is Friday, right?\nB: Yes, so I will work on it tonight.",
            "question": "When is the deadline for the report?",
            "expected_answer": "Friday.",
            "level": "A2",
        },
        {
            "dialog_text": "A: Why are you late today?\nB: The train was delayed because of strong wind.\nA: Oh, that happens sometimes.\nB: I should leave home earlier next time.",
            "question": "Why was the speaker late?",
            "expected_answer": "The train was delayed due to strong wind.",
            "level": "B1",
        },
        {
            "dialog_text": "A: Should we eat Italian or Japanese food tonight?\nB: I had sushi yesterday, so Italian sounds better.\nA: Great. There's a new pasta place near the station.\nB: Let's go there at seven.",
            "question": "What kind of food will they eat?",
            "expected_answer": "Italian food / pasta.",
            "level": "B1",
        },
        {
            "dialog_text": "A: Can you join the volunteer event next month?\nB: I want to, but I have part-time work on weekends.\nA: It's on a weekday evening.\nB: Then I can join.",
            "question": "Why can the second speaker join the event?",
            "expected_answer": "Because it is on a weekday evening, not a weekend.",
            "level": "B1",
        },
        {
            "dialog_text": "A: I lost my umbrella on the bus.\nB: Did you ask the driver?\nA: Yes, but nobody found it.\nB: You can buy a cheap one at the convenience store.",
            "question": "What happened to the umbrella?",
            "expected_answer": "It was lost on the bus.",
            "level": "A2",
        },
        {
            "dialog_text": "A: The museum is free for students today.\nB: Really? I have my student ID with me.\nA: Perfect. Let's go after lunch.\nB: Sounds good.",
            "question": "Why is today a good day to visit the museum?",
            "expected_answer": "It is free for students today.",
            "level": "B1",
        },
        {
            "dialog_text": "A: How was your presentation?\nB: I was nervous at first, but the teacher said it was clear.\nA: That's great!\nB: I practiced a lot last night.",
            "question": "What did the teacher say about the presentation?",
            "expected_answer": "It was clear.",
            "level": "B1",
        },
        {
            "dialog_text": "A: Do you want to take the early or late flight?\nB: The early one arrives before noon, so I can rest in the afternoon.\nA: Then let's book the early flight.\nB: Please do.",
            "question": "Why does the second speaker prefer the early flight?",
            "expected_answer": "It arrives before noon so they can rest in the afternoon.",
            "level": "B2",
        },
    ],
    "D": [
        {
            "passage_text": "Many schools now ask students to bring their own water bottles. This reduces plastic waste from single-use bottles and helps students stay hydrated during class.",
            "question": "Why do schools ask students to bring water bottles?",
            "expected_answer": "To reduce plastic waste and help students stay hydrated.",
            "level": "A2",
        },
        {
            "passage_text": "Last summer, Mia volunteered at a local animal shelter. She cleaned cages, walked dogs, and helped visitors choose pets. She says the experience taught her responsibility.",
            "question": "What did Mia learn from volunteering?",
            "expected_answer": "Responsibility.",
            "level": "A2",
        },
        {
            "passage_text": "Public libraries are changing. Besides books, many now offer free Wi-Fi, study rooms, and workshops on digital skills. They have become community learning centers.",
            "question": "Besides books, what do many libraries offer?",
            "expected_answer": "Free Wi-Fi, study rooms, and digital skills workshops.",
            "level": "B1",
        },
        {
            "passage_text": "Eating breakfast can improve concentration at school. Students who skip breakfast often feel tired before lunch and may find it harder to focus on difficult tasks.",
            "question": "What problem can skipping breakfast cause?",
            "expected_answer": "Feeling tired and difficulty concentrating.",
            "level": "B1",
        },
        {
            "passage_text": "In some cities, bike-sharing systems let people rent bicycles for short trips. Users unlock a bike with an app, ride to their destination, and return it to any station nearby.",
            "question": "How do users unlock a shared bicycle?",
            "expected_answer": "With an app.",
            "level": "B1",
        },
        {
            "passage_text": "Soft skills such as teamwork and clear communication are valued by many employers. Technical knowledge is important, but working well with others often decides who gets promoted.",
            "question": "According to the passage, what often decides who gets promoted?",
            "expected_answer": "Working well with others / soft skills.",
            "level": "B2",
        },
        {
            "passage_text": "A small park opened near the station last month. It has benches, trees, and a playground. Local residents say it gives children a safe place to play after school.",
            "question": "What do local residents say about the park?",
            "expected_answer": "It gives children a safe place to play after school.",
            "level": "A2",
        },
        {
            "passage_text": "Online learning allows students to review lessons at their own pace. However, it also requires self-discipline, because there is less direct supervision from teachers.",
            "question": "What does online learning require from students?",
            "expected_answer": "Self-discipline.",
            "level": "B1",
        },
        {
            "passage_text": "Scientists are developing packaging made from plants instead of plastic. These materials can break down more easily in nature, which may reduce pollution in oceans and rivers.",
            "question": "Why might plant-based packaging help the environment?",
            "expected_answer": "It can break down more easily and reduce pollution.",
            "level": "B2",
        },
        {
            "passage_text": "When Ken moved to a new city, he joined a community sports club. Playing weekly games helped him make friends quickly and feel less lonely.",
            "question": "How did the sports club help Ken?",
            "expected_answer": "He made friends and felt less lonely.",
            "level": "B1",
        },
    ],
    "E": [
        {
            "story_text": "Sara forgot her lunch at home. At school, her friend shared a sandwich with her. Sara felt thankful and decided to bring cookies for everyone the next day.",
            "level": "A2",
            "time_limit_sec": 30,
        },
        {
            "story_text": "One morning, a boy found a lost puppy in the park. He took it to a nearby clinic and posted a photo online. That evening, the owner came to pick it up and thanked him.",
            "level": "A2",
            "time_limit_sec": 30,
        },
        {
            "story_text": "Yuki wanted to improve her English, so she started listening to short podcasts on the train. After three months, she could follow simple conversations more easily and felt more confident in class.",
            "level": "B1",
            "time_limit_sec": 30,
        },
        {
            "story_text": "During a school trip, the bus broke down on a mountain road. While waiting for help, students sang songs and shared snacks. Later they said the unexpected delay became their favorite memory.",
            "level": "B1",
            "time_limit_sec": 30,
        },
        {
            "story_text": "Leo was nervous about speaking in front of the class. He practiced every night with his sister. On the day of the speech, he still felt nervous, but he finished clearly and received warm applause.",
            "level": "B1",
            "time_limit_sec": 30,
        },
        {
            "story_text": "A local bakery was about to close because few customers came. High school students created posters and promoted it on social media. Within weeks, the bakery became busy again and stayed open.",
            "level": "B2",
            "time_limit_sec": 30,
        },
        {
            "story_text": "After missing the last train, Ana walked to a late-night cafe and called her brother. He picked her up thirty minutes later. She promised herself to check the timetable more carefully next time.",
            "level": "B1",
            "time_limit_sec": 30,
        },
        {
            "story_text": "Two classmates argued about a group project. Their teacher asked them to list each person's strengths and divide the work again. The project improved, and they learned to communicate before problems grew.",
            "level": "B2",
            "time_limit_sec": 30,
        },
        {
            "story_text": "When a typhoon canceled the sports festival, the school held a smaller indoor event instead. Students invented new games for the gym. Many said it was more fun than the original plan.",
            "level": "B1",
            "time_limit_sec": 30,
        },
        {
            "story_text": "Mark planted vegetables on his balcony. At first, nothing grew well because he watered them too much. After reading a guide and changing his routine, he finally harvested tomatoes in late summer.",
            "level": "B2",
            "time_limit_sec": 30,
        },
    ],
    "F": [
        {"prompt": "Talk about a hobby you enjoy and why you like it.", "level": "A2", "time_limit_sec": 30},
        {"prompt": "Describe your ideal weekend.", "level": "A2", "time_limit_sec": 30},
        {"prompt": "What is an important skill for students today? Explain your opinion.", "level": "B1", "time_limit_sec": 30},
        {"prompt": "Should students have part-time jobs? Give your opinion and reasons.", "level": "B1", "time_limit_sec": 30},
        {"prompt": "Talk about a place you want to visit and what you would do there.", "level": "A2", "time_limit_sec": 30},
        {"prompt": "How can people reduce stress in daily life? Share your ideas.", "level": "B1", "time_limit_sec": 30},
        {"prompt": "Is it better to study alone or with friends? Explain why.", "level": "B1", "time_limit_sec": 30},
        {"prompt": "What change would you like to see in your school or community?", "level": "B2", "time_limit_sec": 30},
        {"prompt": "Talk about a person who has influenced you.", "level": "B1", "time_limit_sec": 30},
        {"prompt": "Do you think technology makes life better? Give reasons for your answer.", "level": "B2", "time_limit_sec": 30},
    ],
}
