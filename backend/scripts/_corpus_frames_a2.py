"""Tranche A2 autorado del corpus de listening (Fase 3, primera entrega).

Banda auditada A2: velocidad 130-135 wpm, dificultad escalar 2..3 (media del
vector), máx. 15 palabras por script, acento variado y sin connected_speech.
Frases de nivel elemental: pasado simple y continuo, comparativos, pedidos
corteses, instrucciones de dos pasos y microconversaciones.

Un frame es un ítem casi completo; `generate_listening_corpus.py` materializa
id/audio/metadatos y baraja las opciones. El script es la fuente de verdad.
"""

_FACTOR_ORDER = (
    "speed", "vocabulary", "accent", "syntactic", "length", "noise",
    "connected_speech",
)


def _vector(target_sum: int, speaker_count: int = 1) -> dict:
    """Sumas objetivo A2: 12..20 → scalar 2; 21..27 → scalar 3."""
    vec = {f: 1 for f in _FACTOR_ORDER}
    vec["speaker_count"] = speaker_count
    extra = target_sum - (8 + (speaker_count - 1))
    i = 0
    while extra > 0:
        factor = _FACTOR_ORDER[i % len(_FACTOR_ORDER)]
        vec[factor] += 1
        extra -= 1
        i += 1
    return {
        "speed": vec["speed"],
        "vocabulary": vec["vocabulary"],
        "accent": vec["accent"],
        "syntactic": vec["syntactic"],
        "length": vec["length"],
        "speaker_count": vec["speaker_count"],
        "noise": vec["noise"],
        "connected_speech": vec["connected_speech"],
    }


def _frame(
    skill: str,
    topic: str,
    context: str,
    script: str,
    question: str,
    options: list[str],
    *,
    rate: float = 130.0,
    suma: int = 17,
    noise: int = 0,
) -> dict:
    speakers = 2 if context == "conversation" else 1
    return {
        "level": "A2",
        "skill": skill,
        "topic": topic,
        "context": context,
        "script": script,
        "question": question,
        "options": options,
        "answer_index": 0,  # el pipeline baraja después
        "speech_rate": rate,
        "difficulty_vector": _vector(suma, speaker_count=speakers),
        "noise_level": noise,
    }


def _row(
    group: dict,
    script: str,
    question: str,
    answer: str,
    d1: str,
    d2: str,
    d3: str,
) -> dict:
    return _frame(
        group["skill"],
        group["topic"],
        group["context"],
        script,
        question,
        [answer, d1, d2, d3],
        rate=group.get("rate", 130.0),
        suma=group.get("suma", 17),
        noise=group.get("noise", 0),
    )


def _build_rows(group: dict, rows: list[tuple]) -> list[dict]:
    return [
        _row(group, script, question, answer, d1, d2, d3)
        for (script, question, answer, d1, d2, d3) in rows
    ]


FRAMES_A2: list[dict] = []


def _add(group: dict, rows: list[tuple]) -> None:
    FRAMES_A2.extend(_build_rows(group, rows))


# ---------------------------------------------------------------------------
# NUMBERS — horarios, precios, medidas, fechas
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "numbers",
        "topic": "travel",
        "context": "announcement",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("The next train to Manchester departs at ten forty.", "When does the next train to Manchester depart?", "At ten forty", "At ten fourteen", "At nine forty", "At eleven forty"),
        ("Passengers for Dublin should go to gate fourteen.", "Which gate should passengers for Dublin go to?", "Gate fourteen", "Gate forty", "Gate four", "Gate fifteen"),
        ("The coach service to Cardiff runs every thirty minutes.", "How often does the coach to Cardiff run?", "Every thirty minutes", "Every twenty minutes", "Every hour", "Every fifteen minutes"),
        ("Our flight arrives at six twenty in the evening.", "When does the flight arrive?", "At six twenty", "At six twelve", "At seven twenty", "At six forty"),
        ("The platform for the express train is number thirteen.", "Which platform is the express train on?", "Platform thirteen", "Platform thirty", "Platform three", "Platform fourteen"),
        ("The return ticket costs twenty-four pounds.", "How much is the return ticket?", "Twenty-four pounds", "Twenty pounds", "Forty pounds", "Twenty-five pounds"),
        ("We stop at Newcastle for fifteen minutes.", "How long is the stop at Newcastle?", "Fifteen minutes", "Five minutes", "Fifty minutes", "Twenty minutes"),
        ("The night bus leaves at eleven fifty-five.", "When does the night bus leave?", "At eleven fifty-five", "At eleven fifteen", "At eleven forty-five", "At twelve fifteen"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "shopping",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: How much is this jacket? B: It was sixty pounds, but it's forty now.", "How much is the jacket now?", "Forty pounds", "Sixty pounds", "Sixteen pounds", "Fifty pounds"),
        ("A: I'd like half a kilo of tomatoes, please. B: That's two pounds.", "How many tomatoes does the customer want?", "Half a kilo", "One kilo", "Two kilos", "A quarter kilo"),
        ("A: Can I get a discount? B: Sorry, the price is fixed.", "What does the customer ask for?", "A discount", "A refund", "A receipt", "A bigger bag"),
        ("A: These shoes are ninety pounds? B: Yes, but the other pair is thirty.", "How much are the other pair of shoes?", "Thirty pounds", "Ninety pounds", "Thirteen pounds", "Forty pounds"),
        ("A: The blue lamp is cheaper than the red one. B: I'll take the blue one.", "Why does the customer take the blue lamp?", "It's cheaper", "It's bigger", "It's newer", "It's brighter"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "education",
        "context": "message",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("The history exam is on the fourteenth of May.", "When is the history exam?", "On the fourteenth of May", "On the fourth of May", "On the fortieth of May", "On the fourteenth of March"),
        ("You need to read chapters one to five for Monday.", "How many chapters must you read?", "Five", "One", "Fifteen", "Four"),
        ("The course costs one hundred and twenty euros.", "How much does the course cost?", "One hundred and twenty euros", "One hundred euros", "Two hundred euros", "One hundred and twelve euros"),
        ("The science fair starts at ten and finishes at three.", "When does the science fair finish?", "At three", "At ten", "At four", "At half past three"),
        ("Your homework is on page forty-one, exercises two and three.", "Which exercises are the homework?", "Two and three", "One and two", "Three and four", "Two and four"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "work",
        "context": "message",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("The report is due on Friday the twenty-first.", "When is the report due?", "On Friday the twenty-first", "On Friday the twentieth", "On Friday the twenty-second", "On Thursday the twenty-first"),
        ("We need forty chairs and twenty tables for the event.", "How many chairs do they need?", "Forty", "Fourteen", "Twenty", "Thirty"),
        ("Please arrive thirty minutes before the meeting starts.", "How early should you arrive?", "Thirty minutes early", "Thirteen minutes early", "Twenty minutes early", "An hour early"),
        ("The invoice number is two thousand and five.", "What is the invoice number?", "Two thousand and five", "Two hundred and five", "Two thousand and fifty", "Two thousand five hundred"),
        ("Each box contains twelve bottles.", "How many bottles are in each box?", "Twelve", "Twenty", "Ten", "Twenty-four"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "free_time",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: When is your birthday? B: It's on the third of July.", "When is the woman's birthday?", "On the third of July", "On the thirteenth of July", "On the third of June", "On the thirtieth of July"),
        ("A: How long is the film? B: About two hours and a half.", "How long is the film?", "Two hours and a half", "Two hours", "One hour and a half", "Two hours and a quarter"),
        ("A: How often do you go to the gym? B: Three times a week.", "How often does the man go to the gym?", "Three times a week", "Twice a week", "Once a week", "Every day"),
        ("A: What time should I come? B: Around seven thirty.", "When should the woman come?", "Around seven thirty", "At seven", "Around six thirty", "At eight"),
    ],
)

# ---------------------------------------------------------------------------
# DETAIL
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "detail",
        "topic": "travel",
        "context": "announcement",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("The eight o'clock train to Edinburgh has been cancelled.", "Which train has been cancelled?", "The eight o'clock train to Edinburgh", "The eight o'clock train to Glasgow", "The nine o'clock train to Edinburgh", "The eight thirty train to Edinburgh"),
        ("Passengers travelling to Bristol should change at Reading.", "Where should passengers for Bristol change?", "At Reading", "At London", "At Bristol", "At Oxford"),
        ("The café on platform one serves breakfast until eleven.", "Where is the café?", "On platform one", "On platform two", "Next to the ticket office", "At the main entrance"),
        ("Your luggage can be left at the desk on the ground floor.", "Where can luggage be left?", "At the desk on the ground floor", "At the desk on the first floor", "On platform three", "At the taxi rank"),
        ("The train has first class at the front and standard at the back.", "Where is first class?", "At the front", "At the back", "In the middle", "On the upper floor"),
        ("Bus number twenty-two goes to the university every ten minutes.", "Where does bus twenty-two go?", "To the university", "To the hospital", "To the station", "To the market"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "food",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: What do you want for dinner? B: I'll make a salad with chicken.", "What will the woman make for dinner?", "A salad with chicken", "A salad with fish", "Soup with chicken", "Pasta with vegetables"),
        ("A: Is there milk in the fridge? B: There's a little, but it's old.", "What does the man say about the milk?", "It's old", "It's fresh", "It's cold", "There is none"),
        ("A: How do you cook this rice? B: Boil it for ten minutes.", "How long should the rice boil?", "Ten minutes", "Twenty minutes", "Five minutes", "Fifteen minutes"),
        ("A: Does the cake have nuts? B: No, but it has chocolate.", "What does the cake have?", "Chocolate", "Nuts", "Fruit", "Cream"),
        ("A: Where did you buy this cheese? B: At the market in town.", "Where did the woman buy the cheese?", "At the market in town", "At the supermarket", "At the shop next door", "Online"),
        ("A: Would you like dessert? B: Yes, I'll have the fruit salad.", "What will the man have for dessert?", "Fruit salad", "Ice cream", "Cake", "Nothing"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "work",
        "context": "narrative",
        "rate": 130.0,
        "suma": 17,
    },
    [
        ("Laura works as a nurse at the city hospital.", "Where does Laura work?", "At the city hospital", "At a clinic", "At a school", "At a pharmacy"),
        ("The new manager starts on the first of next month.", "When does the new manager start?", "On the first of next month", "Next week", "On the first of this month", "In two months"),
        ("Mr Smith retired last year after thirty years at the bank.", "How long did Mr Smith work at the bank?", "Thirty years", "Thirteen years", "Three years", "Twenty years"),
        ("Our office moved to a new building near the park.", "Where is the new office?", "Near the park", "In the city centre", "Near the station", "At the airport"),
        ("The team meets every Monday morning at nine.", "When does the team meet?", "Every Monday morning", "Every Friday morning", "Every Monday afternoon", "Every Tuesday morning"),
        ("She asked for a day off next Friday.", "When does she want a day off?", "Next Friday", "Tomorrow", "Next Monday", "This Friday"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "education",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: When is our next English test? B: On the second of June, I think.", "When is the next English test?", "On the second of June", "On the twelfth of June", "On the second of July", "Next week"),
        ("A: Who teaches the chemistry class? B: Dr Parker, the new teacher.", "Who teaches chemistry?", "Dr Parker", "Mrs Brown", "Mr Lee", "The new student"),
        ("A: Did you finish the project? B: Almost. I just need the pictures.", "What does the student still need?", "Pictures", "The text", "The charts", "The numbers"),
        ("A: Can I borrow your dictionary? B: Sorry, I left it at home.", "Why can't the student borrow the dictionary?", "It's at home", "It's lost", "It's broken", "He's using it"),
        ("A: What did you learn today? B: We learned about the planets.", "What did the students learn about?", "The planets", "The weather", "Old cars", "Sea animals"),
        ("A: How was the exam? B: It was difficult, but I think I passed.", "How did the student do on the exam?", "They think they passed", "They failed", "They didn't go", "It was easy"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "shopping",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: This shirt is small. Do you have a larger size? B: Yes, here.", "Which size does the customer need?", "A larger size", "A smaller size", "The same size", "A different colour"),
        ("A: When does the sale end? B: On Sunday night.", "When does the sale end?", "On Sunday night", "On Saturday night", "On Monday night", "Tomorrow morning"),
        ("A: The red dress is cheaper than the blue one. B: I prefer the blue one anyway.", "Which dress does the woman prefer?", "The blue one", "The red one", "The cheapest one", "Neither"),
        ("A: Do you sell phone chargers here? B: Yes, they're next to the headphones.", "Where are the phone chargers?", "Next to the headphones", "Next to the phones", "At the door", "Behind the counter"),
        ("A: This bag is made of leather, right? B: Actually, it's made of plastic.", "What is the bag made of?", "Plastic", "Leather", "Paper", "Cotton"),
        ("A: Can I try on these jeans? B: Of course. The changing rooms are free now.", "What does the customer want to do?", "Try on jeans", "Buy jeans", "Return jeans", "Find the jeans"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "free_time",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("We planned a picnic, but it rained all afternoon.", "What happened to the picnic?", "It rained", "They cancelled it", "They ate indoors", "The park was closed"),
        ("Tom watched a football game and then cooked dinner.", "What did Tom do after the game?", "He cooked dinner", "He watched another game", "He went to bed", "He went out"),
        ("Emma joined a photography club last month.", "When did Emma join the photography club?", "Last month", "Last week", "Last year", "Yesterday"),
        ("They go camping every summer by the lake.", "Where do they go camping?", "By the lake", "In the forest", "On the beach", "In the mountains"),
        ("Jack spent his weekend fixing his old bike.", "What did Jack do at the weekend?", "He fixed his bike", "He bought a bike", "He washed his bike", "He sold his bike"),
        ("We had a great time at the beach despite the wind.", "How was the time at the beach?", "Great", "Terrible", "Boring", "Short"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "daily_routine",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("Yesterday Anna left home earlier than usual.", "Why did Anna leave home early?", "Earlier than usual", "Because she was late", "Because it was cold", "Because she was ill"),
        ("Ben usually walks to work, but today he took the bus.", "How did Ben go to work today?", "By bus", "On foot", "By car", "By bike"),
        ("Maria drinks tea after lunch every day.", "When does Maria drink tea?", "After lunch", "Before breakfast", "At night", "After dinner"),
        ("Dad waters the plants when he gets home.", "When does Dad water the plants?", "When he gets home", "In the morning", "Before work", "At the weekend"),
        ("Sara forgot her keys and waited outside for an hour.", "Why did Sara wait outside?", "She forgot her keys", "She lost her phone", "She missed the bus", "She was early"),
        ("Peter goes to bed later at the weekend.", "When does Peter go to bed later?", "At the weekend", "On weekdays", "In winter", "On Mondays"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "weather",
        "context": "news",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("Heavy rain is expected across the north tonight.", "Where will the heavy rain be?", "In the north", "In the south", "In the east", "Everywhere"),
        ("Temperatures will drop below zero in the morning.", "When will temperatures drop below zero?", "In the morning", "At noon", "Tonight", "This afternoon"),
        ("The storm caused problems on the roads this morning.", "What did the storm cause?", "Problems on the roads", "A power cut", "Closed schools", "A flood"),
        ("Strong winds arrive on Friday afternoon.", "When will the strong winds arrive?", "On Friday afternoon", "On Thursday afternoon", "On Friday morning", "On Saturday afternoon"),
        ("The weekend will be dry and warmer than today.", "What will the weekend weather be like?", "Dry and warmer", "Wet and cold", "Windy and cool", "Cloudy and dry"),
        ("Fog is expected near the coast in the early morning.", "Where is fog expected?", "Near the coast", "In the mountains", "In the city", "Near the airport"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "sports",
        "context": "narrative",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("The home team won the match by three goals to one.", "What was the final score?", "Three goals to one", "One goal to three", "Two goals to one", "Three goals to zero"),
        ("The tennis player trained for four hours before the final.", "How long did the player train?", "Four hours", "Two hours", "Three hours", "An hour"),
        ("Our running club meets at the park every Tuesday evening.", "When does the running club meet?", "Every Tuesday evening", "Every Thursday evening", "Every Saturday morning", "Every Monday evening"),
        ("The goalkeeper saved two penalties in the last game.", "What did the goalkeeper do?", "Saved two penalties", "Scored two goals", "Missed two penalties", "Left the game"),
        ("She broke her arm and couldn't play for a month.", "Why couldn't she play for a month?", "She broke her arm", "She was too tired", "She had no time", "She moved away"),
    ],
)

# ---------------------------------------------------------------------------
# GIST
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "gist",
        "topic": "functional",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: I can't find my glasses anywhere. B: Check the kitchen table.", "What is the problem?", "The man lost his glasses", "The man broke his glasses", "The man needs new glasses", "The glasses are expensive"),
        ("A: My phone doesn't work. B: Maybe the battery is dead.", "What does the woman suggest?", "The battery may be dead", "Buying a new phone", "Calling the shop", "Turning off the phone"),
        ("A: Can you tell me how this machine works? B: Press this button first.", "What does the man want to know?", "How the machine works", "The price of the machine", "Where the machine is", "Who made the machine"),
        ("A: I missed the bus again. B: You should leave home earlier.", "What advice does the woman give?", "Leave home earlier", "Take a taxi", "Buy a car", "Walk to work"),
        ("A: The printer is out of paper. B: There's more paper in the cupboard.", "What is the problem?", "The printer has no paper", "The printer is broken", "The printer is off", "The printer is too slow"),
        ("A: I locked myself out of the flat. B: Call the building manager.", "What happened to the man?", "He locked himself out", "He lost his keys inside", "He broke the door", "He forgot his address"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "travel",
        "context": "conversation",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("A: I'd like a room for two nights. B: We have a room with a sea view.", "What does the man want?", "A room for two nights", "A room for one night", "A table for two", "A ticket"),
        ("A: What time is the tour? B: It leaves at ten from the main square.", "Where does the tour leave from?", "The main square", "The hotel", "The station", "The museum"),
        ("A: How far is the beach? B: About twenty minutes on foot.", "How far is the beach?", "Twenty minutes on foot", "Two hours on foot", "Twenty minutes by car", "Two minutes on foot"),
        ("A: Can you recommend a good restaurant? B: There's a nice one near the harbour.", "What does the tourist want?", "A restaurant recommendation", "A hotel", "A map", "A taxi"),
        ("A: I lost my boarding pass. B: Don't worry. Show your passport at the desk.", "What should the passenger do?", "Show their passport at the desk", "Buy a new ticket", "Go home", "Call the airline"),
        ("A: Is the museum open on Mondays? B: No, it opens from Tuesday to Sunday.", "When is the museum closed?", "On Mondays", "At the weekend", "On Tuesdays", "In winter"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "work",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: Could you cover my shift on Friday? B: I'm free on Friday, so yes.", "What does the woman ask for?", "Cover for her shift", "A day off", "A promotion", "Help with a report"),
        ("A: Have you seen the new email? B: Yes, the meeting moved to Thursday.", "What happened to the meeting?", "It moved to Thursday", "It was cancelled", "It moved to Tuesday", "It starts later"),
        ("A: The client wants to see the design today. B: I'll finish it by three.", "When will the design be ready?", "By three", "Today at noon", "Tomorrow", "By five"),
        ("A: Who is going to present the project? B: I think Mark is.", "Who will present the project?", "Mark", "The woman", "The manager", "Nobody yet"),
        ("A: Do you have the figures for last month? B: They're on my desk.", "What does the man ask for?", "The figures for last month", "A new computer", "The client's address", "A report from the boss"),
        ("A: My computer is very slow today. B: Try restarting it first.", "What should the woman do?", "Restart her computer", "Buy a new computer", "Call IT", "Work at home"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "free_time",
        "context": "message",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("We're going for a walk in the hills on Saturday. Join us if you can!", "What is the message about?", "A walk in the hills", "A party", "A football match", "A picnic by the river"),
        ("The book club meets next Wednesday at the library.", "Where does the book club meet?", "At the library", "At a café", "At someone's home", "At school"),
        ("I got two tickets for the theatre, but Anna can't come.", "Why does the speaker have an extra ticket?", "Anna can't come", "The show is cheap", "The speaker bought two", "The show was cancelled"),
        ("There's a free yoga class in the park on Sunday morning.", "What is happening on Sunday morning?", "A free yoga class", "A concert", "A market", "A race"),
        ("Let's meet for coffee before the film starts.", "What is the plan?", "Coffee before the film", "Coffee after the film", "Dinner before the film", "Coffee at home"),
        ("The chess club needs new members. Come and play with us!", "What is the message about?", "The chess club", "A chess competition", "A new game", "A school club fair"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "education",
        "context": "message",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("Don't forget your lab coat for the science class tomorrow.", "What should you remember?", "Your lab coat", "Your homework", "Your books", "Your lunch"),
        ("The library will be closed on Thursday for maintenance.", "Why will the library be closed?", "For maintenance", "For a holiday", "For exams", "It's being painted"),
        ("Your essay must be at least two pages long.", "What is the requirement for the essay?", "At least two pages", "Exactly two pages", "One page", "Three pages"),
        ("The school trip to the science museum is on the twenty-fifth.", "When is the school trip?", "On the twenty-fifth", "On the twenty-second", "Next month", "On Friday"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "weather",
        "context": "news",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("A cold front is moving in from the west tonight.", "What is the news about?", "A cold front", "A storm warning", "Heavy snow", "High winds"),
        ("The heatwave will continue until the weekend.", "How long will the heatwave last?", "Until the weekend", "For one more day", "Until next month", "For two weeks"),
        ("Flights may be delayed because of the heavy fog.", "Why may flights be delayed?", "Because of the fog", "Because of the rain", "Because of the wind", "Because of the snow"),
        ("Drivers should be careful on the icy roads this morning.", "What should drivers do?", "Be careful on the roads", "Stay at home", "Use the train", "Drive faster"),
    ],
)

# ---------------------------------------------------------------------------
# ATTITUDE
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "attitude",
        "topic": "work",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: How was your first day? B: It was better than I expected.", "How does the woman feel about her first day?", "Better than expected", "Worse than expected", "Terrible", "Confusing"),
        ("A: Did the boss like your idea? B: I think so. He smiled the whole time.", "How does the man feel about the meeting?", "Positive", "Worried", "Angry", "Unsure"),
        ("A: You look worried. B: I have a big presentation tomorrow.", "Why is the man worried?", "He has a big presentation", "He lost his job", "He was late", "He has a lot of work"),
        ("A: How was the training? B: Boring, to be honest. Same as every year.", "How did the woman find the training?", "Boring", "Useful", "Interesting", "Too short"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "travel",
        "context": "narrative",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("The hotel room was smaller than the pictures, which was disappointing.", "How did the traveller feel about the room?", "Disappointed", "Amazed", "Pleased", "Surprised"),
        ("Our flight was delayed for five hours, and we were all exhausted.", "How did the travellers feel?", "Exhausted", "Excited", "Relaxed", "Bored"),
        ("The guide was wonderful and the views were amazing. We loved every minute.", "How was the trip?", "Wonderful", "Terrible", "Tiring", "Expensive"),
        ("Losing my passport abroad was a frightening experience.", "How did the speaker feel about losing their passport?", "Frightened", "Calm", "Excited", "Amused"),
        ("The locals were friendly and helped us find our way.", "What did the speaker think of the locals?", "They were friendly", "They were rude", "They were quiet", "They were busy"),
        ("After the long hike, we were tired but very happy.", "How did the hikers feel after the hike?", "Tired but happy", "Too tired to talk", "Sad it ended", "Angry at the guide"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "food",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: How's your steak? B: It's a bit tough, actually.", "What does the man think of the steak?", "It's a bit tough", "It's perfect", "It's too salty", "It's cold"),
        ("A: Did you enjoy the meal? B: The soup was lovely, but the main course was bland.", "How was the main course?", "Bland", "Spicy", "Delicious", "Salty"),
        ("A: What do you think of this café? B: It's nice, but a little noisy.", "What does the woman think of the café?", "Nice but noisy", "Perfect", "Too expensive", "Too quiet"),
        ("A: I'm not a fan of fish. B: Me neither. Let's get pizza.", "How do they feel about fish?", "They don't like it", "They love it", "They want to try it", "They eat it daily"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "daily_routine",
        "context": "message",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("I'm looking forward to the long weekend. I really need a break.", "How does the speaker feel?", "They need a break", "They hate weekends", "They're bored", "They're angry"),
        ("I'm fed up with this cold weather and the dark mornings.", "How does the speaker feel about the weather?", "Fed up", "Happy", "Excited", "Surprised"),
        ("It was a long day, but I feel good about what we did.", "How does the speaker feel about the day?", "Good", "Bad", "Tired of everything", "Nervous"),
        ("I'm proud of myself for finishing the course.", "Why does the speaker feel proud?", "They finished the course", "They won a prize", "They got a job", "They passed the exam"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "shopping",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: How was the shopping? B: Great. I found exactly what I wanted.", "How did the woman feel about the shopping?", "Great", "Tiring", "Disappointing", "Expensive"),
        ("A: Why are you returning this? B: It looks different from the picture.", "Why is the man unhappy?", "The item looks different", "The item is broken", "The item is too small", "The item was late"),
        ("A: Are you happy with your new phone? B: Not really. The battery is poor.", "What does the woman think of the phone?", "The battery is poor", "The screen is small", "It's too heavy", "It's too slow"),
        ("A: The staff here are so helpful. B: Yes, they really know their job.", "What do they think of the staff?", "They're helpful", "They're slow", "They're rude", "They're new"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "free_time",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("We laughed the whole evening. It was so much fun!", "How was the evening?", "Fun", "Quiet", "Long", "Strange"),
        ("The concert was amazing, but the tickets cost a fortune.", "What does the speaker think of the tickets?", "They were very expensive", "They were cheap", "They were free", "They were hard to find"),
        ("I felt nervous at first, but soon I was enjoying myself.", "How did the speaker feel at first?", "Nervous", "Bored", "Angry", "Sleepy"),
        ("The museum was interesting, but we were too tired to enjoy it.", "Why didn't they enjoy the museum?", "They were tired", "It was closed", "It was boring", "It was crowded"),
    ],
)

# ---------------------------------------------------------------------------
# SPEAKER_INTENTION
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "speaker_intention",
        "topic": "food",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: Could I have the menu, please? B: Of course, here you are.", "What does the customer want?", "The menu", "The bill", "Some water", "A table"),
        ("A: Would you like anything else? B: No thanks, just the bill, please.", "What does the man want?", "The bill", "More coffee", "A dessert", "A menu"),
        ("A: Are you ready to order? B: Yes, I'll have the grilled fish.", "What does the woman order?", "Grilled fish", "A salad", "Roast chicken", "Soup"),
        ("A: Could I get this to take away? B: Sure, we'll pack it for you.", "What does the customer want?", "The food to take away", "A table", "The recipe", "A refund"),
        ("A: Can we sit by the window? B: I'm sorry, that table is reserved.", "What does the couple want?", "A table by the window", "A table outside", "The menu", "A quiet table"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "shopping",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: I'd like to exchange this sweater for a smaller one.", "What does the customer want?", "A smaller sweater", "A refund", "A different colour", "A receipt"),
        ("A: Could you tell me when the new books arrive? B: On Thursday morning.", "What does the customer want to know?", "When new books arrive", "How much books cost", "Where the books are", "Which book is popular"),
        ("A: Can I have a bag for these? B: Paper or plastic?", "What does the customer want?", "A bag", "A receipt", "A discount", "Help carrying things"),
        ("A: I'm looking for a gift under twenty pounds.", "What kind of gift does the customer want?", "A gift under twenty pounds", "A gift for a child", "A gift for a man", "The most expensive gift"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "work",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: Could you send the minutes to everyone? B: Yes, right after the meeting.", "What does the woman want?", "The minutes sent to everyone", "A shorter meeting", "A new schedule", "A day off"),
        ("A: I'd like to book a meeting room for Tuesday.", "What does the man want?", "A meeting room for Tuesday", "A new computer", "Help with a report", "A parking space"),
        ("A: Can you check the client's email for me? B: I'll look right now.", "What does the woman ask?", "To check the client's email", "To write a new email", "To call the client", "To print an email"),
        ("A: Would you mind working this Saturday? B: I can, but only in the morning.", "What does the manager ask?", "To work on Saturday", "To work at night", "To work from home", "To take a holiday"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "travel",
        "context": "conversation",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("A: Could you recommend a hotel near the station? B: The Grand is very good.", "What does the tourist want?", "A hotel near the station", "A map of the city", "A train ticket", "A taxi"),
        ("A: Can I book two seats on the nine o'clock train?", "What does the passenger want?", "Two seats on the nine o'clock train", "A return ticket", "A window seat", "A quiet coach"),
        ("A: Where can I rent a car? B: There's an office at the airport.", "What does the man want to do?", "Rent a car", "Buy a car", "Park his car", "Fix his car"),
        ("A: Could you take a photo of us, please? B: Of course. Say cheese!", "What do the tourists want?", "A photo", "Directions", "A souvenir", "The bill"),
        ("A: I'd like to cancel my booking for tonight.", "What does the guest want?", "To cancel the booking", "To change the date", "A late check-out", "An extra bed"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "functional",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: Can you turn down the music? I'm trying to study.", "What does the man want?", "The music turned down", "The music louder", "Help studying", "The window closed"),
        ("A: Could you move your car? It's blocking the gate.", "What does the woman want?", "The car moved", "A ride home", "Help parking", "The car keys"),
        ("A: Can I leave my bag here for an hour? B: Yes, put it behind the desk.", "What does the man want?", "To leave his bag", "To buy a bag", "To open his bag", "Help with his bag"),
        ("A: Could you hold the door, please? B: Of course.", "What does the woman want?", "Someone to hold the door", "Someone to call a taxi", "Help with her bags", "The door closed"),
        ("A: Would you mind helping me with this form? B: Not at all.", "What does the man need help with?", "A form", "A computer", "A box", "A map"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "education",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: Could you explain this exercise again? B: Sure, listen carefully.", "What does the student want?", "The exercise explained again", "More homework", "A new book", "The answer"),
        ("A: Can I hand in my essay tomorrow? B: Yes, but it will lose marks.", "What does the student ask?", "To hand in the essay tomorrow", "An extension of a week", "To rewrite the essay", "A higher mark"),
        ("A: Do you have any notes from yesterday's class? B: I can share mine.", "What does the student want?", "Notes from the class", "The homework", "The teacher's email", "A new pen"),
        ("A: Could you tell me where the biology lab is? B: It's on the second floor.", "What does the student want to know?", "Where the biology lab is", "When biology class starts", "Who teaches biology", "What lab work is due"),
    ],
)

# ---------------------------------------------------------------------------
# VOCABULARY
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "vocabulary",
        "topic": "travel",
        "context": "announcement",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("The departure time has changed to three thirty.", "Which word means 'hora de salida'?", "departure time", "arrival time", "flight time", "gate"),
        ("Please keep your luggage with you at all times.", "Which word means 'equipaje'?", "luggage", "ticket", "passport", "seat"),
        ("The plane is boarding at gate five now.", "Which word means 'embarcando'?", "boarding", "landing", "leaving", "waiting"),
        ("Passengers should arrive at the airport two hours early.", "Which word means 'llegar'?", "arrive", "leave", "depart", "travel"),
        ("The journey takes about three hours by coach.", "Which word means 'viaje' / 'trayecto'?", "journey", "ticket", "driver", "station"),
        ("We apologize for the delay of this service.", "Which word means 'retraso'?", "delay", "change", "stop", "speed"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "work",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("The manager asked everyone to attend the meeting.", "Which word means 'asistir'?", "attend", "cancel", "leave", "plan"),
        ("She works for an international company.", "Which word means 'empresa'?", "company", "school", "bank", "hospital"),
        ("He earns a good salary in his new job.", "Which word means 'salario'?", "salary", "price", "bill", "cost"),
        ("The deadline for the project is next Friday.", "Which word means 'fecha límite'?", "deadline", "holiday", "meeting", "break"),
        ("Please sign the document at the bottom.", "Which word means 'firmar'?", "sign", "read", "print", "send"),
        ("Our branch opens a new office in Leeds.", "Which word means 'sucursal' / 'oficina'?", "branch", "house", "floor", "desk"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "free_time",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("We spent the afternoon wandering around the old town.", "Which word means 'paseando sin rumbo'?", "wandering", "running", "driving", "waiting"),
        ("She collects stamps from different countries.", "Which word means 'colecciona'?", "collects", "buys", "reads", "draws"),
        ("The view from the top of the hill was amazing.", "Which word means 'vista' / 'panorama'?", "view", "road", "field", "house"),
        ("He enjoys chatting with his neighbours.", "Which word means 'charlar'?", "chatting", "shouting", "working", "arguing"),
        ("I joined a book club last year.", "Which word means 'me uní'?", "joined", "left", "opened", "found"),
        ("The game was exciting from start to finish.", "Which word means 'emocionante'?", "exciting", "boring", "short", "easy"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "food",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("Stir the soup slowly so it doesn't burn.", "Which word means 'remueve'?", "stir", "cut", "pour", "eat"),
        ("The sauce tasted a little bitter.", "Which word means 'amargo'?", "bitter", "sweet", "sour", "spicy"),
        ("We ordered a main course and a dessert.", "Which word means 'plato principal'?", "main course", "starter", "drink", "side dish"),
        ("This knife is too blunt to cut the bread.", "Which word means 'roma' / 'sin filo'?", "blunt", "sharp", "long", "heavy"),
        ("The waiter recommended the fish of the day.", "Which word means 'recomendó'?", "recommended", "served", "cooked", "offered"),
        ("Add a pinch of salt to the eggs.", "Which word means 'pellizco' (una pizca)?", "pinch", "cup", "bag", "plate"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "daily_routine",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("I usually go for a run before work.", "Which word means 'normalmente'?", "usually", "never", "rarely", "sometimes"),
        ("She tidies her room every Sunday.", "Which word means 'ordena' / 'recoge'?", "tidies", "opens", "paints", "rents"),
        ("He overslept and missed the bus.", "Which word means 'se quedó dormido'?", "overslept", "woke up", "got ready", "went out"),
        ("We usually have a quick snack in the afternoon.", "Which word means 'aperitivo' / 'tentempié'?", "snack", "meal", "feast", "treat"),
        ("She glances at her phone every few minutes.", "Which word means 'echa un vistazo'?", "glances", "stares", "locks", "drops"),
        ("I need to recharge my phone every day.", "Which word means 'recargar'?", "recharge", "repair", "replace", "reset"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "education",
        "context": "narrative",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("The teacher divided the class into small groups.", "Which word means 'dividió'?", "divided", "joined", "filled", "opened"),
        ("You should revise the grammar before the test.", "Which word means 'repasar'?", "revise", "forget", "learn", "skip"),
        ("She takes notes during every lecture.", "Which word means 'apuntes'?", "notes", "books", "photos", "breaks"),
        ("The students discussed the topic in pairs.", "Which word means 'discutieron' / 'hablaron de'?", "discussed", "ignored", "read", "memorized"),
        ("The course covers speaking and writing.", "Which word means 'abarca' / 'cubre'?", "covers", "starts", "finishes", "skips"),
        ("He passed the exam with a good mark.", "Which word means 'aprobó'?", "passed", "failed", "took", "wrote"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "shopping",
        "context": "conversation",
        "rate": 130.0,
        "suma": 13,
    },
    [
        ("A: Do you have a receipt for this? B: Yes, here it is.", "Which word means 'recibo' / 'ticket'?", "receipt", "basket", "counter", "label"),
        ("A: This coat is on sale this week. B: Great, I'll take it.", "Which word means 'rebajado' / 'en oferta'?", "on sale", "in stock", "new in", "out of date"),
        ("A: Is the shirt in stock? B: Sorry, only in blue.", "Which word means 'en stock'?", "in stock", "sold out", "on sale", "out of order"),
        ("A: Can I have a refund, please? B: Do you have the receipt?", "Which word means 'reembolso'?", "refund", "exchange", "discount", "gift"),
        ("A: The trousers are a bit loose. B: Try a smaller size.", "Which word means 'holgados'?", "loose", "tight", "short", "worn"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "weather",
        "context": "news",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("The temperature will drop sharply overnight.", "Which word means 'descender'?", "drop", "rise", "stay", "turn"),
        ("A shower is expected later in the afternoon.", "Which word means 'chaparrón'?", "shower", "sunshine", "storm", "fog"),
        ("The roads are slippery after the rain.", "Which word means 'resbaladizas'?", "slippery", "dry", "clean", "busy"),
        ("The forecast says it will clear up by noon.", "Which word means 'pronóstico'?", "forecast", "news", "report", "warning"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "functional",
        "context": "instructions",
        "rate": 133.0,
        "suma": 17,
    },
    [
        ("Insert the card into the machine.", "Which word means 'introduce' / 'inserta'?", "insert", "remove", "press", "turn"),
        ("Follow the instructions on the screen.", "Which word means 'sigue' / 'instrucciones'?", "instructions", "questions", "buttons", "letters"),
        ("Make sure the door is locked before you leave.", "Which word means 'cerrada con llave'?", "locked", "open", "broken", "clean"),
        ("Wait for the light to turn green.", "Which word means 'espera'?", "wait", "run", "press", "hurry"),
    ],
)

# Rebalance de dificultad dentro de banda: los grupos con anuncios largos,
# noticias o frases de dos cláusulas suben a scalar 3 (suma 21) para que la ruta
# A2 mezcle dificultades 2 y 3 dentro de su banda auditada.
_REBALANCE_A2: dict[tuple[str, str], int] = {
    ("numbers", "travel"): 21,
    ("numbers", "work"): 21,
    ("detail", "travel"): 21,
    ("detail", "weather"): 21,
    ("detail", "sports"): 21,
    ("gist", "travel"): 21,
    ("gist", "weather"): 21,
    ("attitude", "travel"): 21,
    ("vocabulary", "weather"): 21,
    ("vocabulary", "functional"): 21,
}
for _f in FRAMES_A2:
    _tgt = _REBALANCE_A2.get((_f["skill"], _f["topic"]))
    if _tgt:
        _f["difficulty_vector"] = _vector(
            _tgt, _f["difficulty_vector"]["speaker_count"]
        )

# ---------------------------------------------------------------------------
# Guards de autoría: bandas auditadas A2 (15 palabras, scalar 2..3).
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    from collections import Counter

    print("A2 frames:", len(FRAMES_A2))
    print("Por skill:", dict(Counter(f["skill"] for f in FRAMES_A2)))
    print("Por topic:", dict(Counter(f["topic"] for f in FRAMES_A2)))
