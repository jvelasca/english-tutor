"""Tranche A1 autorado del corpus de listening (Fase 3, primera entrega).

Contenido auditado para la banda A1 del corpus: velocidad 115-125 wpm,
dificultad escalar 1..2 (media del vector), máx. 14 palabras por script, acento
variado y sin connected_speech. Cada frame declara el script como fuente de
verdad; `generate_listening_corpus.py` materializa id/audio/metadatos y baraja
las opciones.

Formato de cada frame:
    level, skill, topic, context, script, question, options (correcta primero),
    speech_rate, vector, noise_level (0), speaker_count (1 salvo diálogos A:/B:).

Convención de autoría: frases muy breves, vocabulario de supervivencia,
preguntas literales (quién/cuándo/dónde/cuánto/qué quiere) y una única idea.
"""

# Vector de dificultad: se construye a partir de una *suma objetivo* repartida
# entre los 7 factores variables (speaker_count se fija aparte). Sumas A1:
#   8..11 → scalar 1; 12..20 → scalar 2  (media redondeada del vector).
_FACTOR_ORDER = (
    "speed", "vocabulary", "accent", "syntactic", "length", "noise",
    "connected_speech",
)


def _vector(target_sum: int, speaker_count: int = 1) -> dict:
    vec = {f: 1 for f in _FACTOR_ORDER}
    vec["speaker_count"] = speaker_count
    extra = target_sum - (8 + (speaker_count - 1))
    i = 0
    while extra > 0:
        factor = _FACTOR_ORDER[i % len(_FACTOR_ORDER)]
        vec[factor] += 1
        extra -= 1
        i += 1
    # Orden canónico para una escritura estable en el JSON.
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
    rate: float = 120.0,
    suma: int = 11,
    noise: int = 0,
) -> dict:
    speakers = 2 if context == "conversation" else 1
    return {
        "level": "A1",
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
    """Un ítem desde una fila compacta (respuesta + 3 distractores)."""
    return _frame(
        group["skill"],
        group["topic"],
        group["context"],
        script,
        question,
        [answer, d1, d2, d3],
        rate=group.get("rate", 120.0),
        suma=group.get("suma", 11),
        noise=group.get("noise", 0),
    )


def _build_rows(group: dict, rows: list[tuple]) -> list[dict]:
    return [
        _row(group, script, question, answer, d1, d2, d3)
        for (script, question, answer, d1, d2, d3) in rows
    ]


FRAMES_A1: list[dict] = []


def _add(group: dict, rows: list[tuple]) -> None:
    FRAMES_A1.extend(_build_rows(group, rows))


# ---------------------------------------------------------------------------
# NUMBERS — tiempos de salida, andenes, precios, páginas, horarios
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "numbers",
        "topic": "travel",
        "context": "announcement",
        "rate": 120.0,
        "suma": 13,
    },
    [
        ("The bus to the airport leaves at nine fifteen.", "When does the bus to the airport leave?", "At nine fifteen", "At ten fifteen", "At eight fifteen", "At nine thirty"),
        ("The train to Brighton leaves at twelve o'clock.", "When does the train to Brighton leave?", "At twelve o'clock", "At two o'clock", "At eleven o'clock", "At one o'clock"),
        ("The ferry to the island leaves at six thirty.", "When does the ferry leave?", "At six thirty", "At six fifteen", "At seven thirty", "At five thirty"),
        ("Attention, passengers. The coach to Oxford departs at four forty-five.", "When does the coach to Oxford depart?", "At four forty-five", "At four fifteen", "At five forty-five", "At four thirty"),
        ("The last train to the city leaves at eleven twenty.", "When does the last train leave?", "At eleven twenty", "At ten twenty", "At eleven ten", "At twelve twenty"),
        ("Flight two one four leaves at eight o'clock from gate twelve.", "When does flight two one four leave?", "At eight o'clock", "At nine o'clock", "At eight thirty", "At seven o'clock"),
        ("The bus to the stadium leaves from gate three.", "Which gate does the bus leave from?", "Gate three", "Gate one", "Gate five", "Gate six"),
        ("The train to York leaves from platform seven.", "Which platform does the train to York leave from?", "Platform seven", "Platform two", "Platform four", "Platform nine"),
        ("Your coach leaves from bay eight, not bay two.", "Which bay does the coach leave from?", "Bay eight", "Bay two", "Bay five", "Bay three"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "shopping",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: How much is the orange juice? B: It's two pounds fifty.", "How much is the orange juice?", "Two pounds fifty", "One pound fifty", "Two pounds", "Three pounds fifty"),
        ("A: How much are these bananas? B: They're one pound twenty.", "How much are the bananas?", "One pound twenty", "One pound", "Two pounds twenty", "One pound fifty"),
        ("A: What's the price of this book? B: It's twelve pounds.", "How much is the book?", "Twelve pounds", "Ten pounds", "Eleven pounds", "Twenty pounds"),
        ("A: How much is the ticket? B: Adult tickets are six pounds.", "How much is an adult ticket?", "Six pounds", "Five pounds", "Seven pounds", "Eight pounds"),
        ("A: How much is the cheese? B: It's four pounds for this piece.", "How much is the cheese?", "Four pounds", "Three pounds", "Five pounds", "Two pounds"),
        ("The coat is ninety pounds, but today it's seventy.", "How much is the coat today?", "Seventy pounds", "Ninety pounds", "Sixty pounds", "Eighty pounds"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "daily_routine",
        "context": "message",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("Please call me back at five forty-five.", "When should you call back?", "At five forty-five", "At five fifteen", "At six forty-five", "At five thirty"),
        ("Meet me at the station at ten thirty.", "When should you meet the speaker?", "At ten thirty", "At ten fifteen", "At nine thirty", "At eleven thirty"),
        ("My train arrives at eight twenty, not nine.", "When does the train arrive?", "At eight twenty", "At eight", "At nine twenty", "At nine"),
        ("The doctor's appointment is at two o'clock this afternoon.", "When is the appointment?", "At two o'clock", "At three o'clock", "At twelve o'clock", "At four o'clock"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "education",
        "context": "instructions",
        "rate": 120.0,
        "suma": 9,
    },
    [
        ("Open your books, please, and turn to page fifteen.", "Which page should you turn to?", "Page fifteen", "Page fourteen", "Page sixteen", "Page five"),
        ("The maths class starts at nine o'clock.", "When does the maths class start?", "At nine o'clock", "At eight o'clock", "At ten o'clock", "At nine thirty"),
        ("Please write your name on line four.", "Which line should you write your name on?", "Line four", "Line two", "Line six", "Line five"),
        ("Answer questions one to three on page nine.", "Where are the questions to answer?", "On page nine", "On page three", "On page one", "On page six"),
    ],
)

_add(
    {
        "skill": "numbers",
        "topic": "work",
        "context": "message",
        "rate": 120.0,
        "suma": 13,
    },
    [
        ("The shop opens at nine and closes at five thirty.", "When does the shop close?", "At five thirty", "At five", "At four thirty", "At six"),
        ("The office opens at eight thirty and closes at four.", "When does the office open?", "At eight thirty", "At nine", "At eight", "At seven thirty"),
        ("The library is open from ten to six on Saturdays.", "When does the library close on Saturdays?", "At six", "At five", "At seven", "At four"),
        ("Room two twelve is on the second floor.", "Which room is on the second floor?", "Room two twelve", "Room two ten", "Room two twenty", "Room three twelve"),
        ("Our meeting starts at three and finishes at four.", "When does the meeting start?", "At three", "At two", "At four", "At three thirty"),
        ("The supermarket opens at eight on Sundays.", "When does the supermarket open on Sundays?", "At eight", "At nine", "At seven", "At ten"),
    ],
)

# ---------------------------------------------------------------------------
# DETAIL — datos concretos: cantidades, personas, lugares, rutinas
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "detail",
        "topic": "daily_routine",
        "context": "narrative",
        "rate": 115.0,
        "suma": 11,
    },
    [
        ("Katie has three uncles and two aunts.", "How many uncles does Katie have?", "Three", "Two", "Four", "One"),
        ("Tom has a cat and two dogs.", "How many dogs does Tom have?", "Two", "One", "Three", "Four"),
        ("Sara has four classes today.", "How many classes does Sara have today?", "Four", "Three", "Five", "Two"),
        ("Ben drinks two cups of coffee every morning.", "How many cups of coffee does Ben drink?", "Two", "One", "Three", "Four"),
        ("Anna sleeps eight hours every night.", "How many hours does Anna sleep?", "Eight", "Seven", "Six", "Nine"),
        ("Mark works five days a week.", "How many days does Mark work?", "Five", "Four", "Six", "Seven"),
        ("There are three chairs in the kitchen.", "How many chairs are in the kitchen?", "Three", "Two", "Four", "Five"),
        ("Emma has one brother and two sisters.", "How many sisters does Emma have?", "Two", "One", "Three", "Four"),
        ("The bus stops four times before the city.", "How many times does the bus stop?", "Four", "Three", "Five", "Two"),
        ("James drinks water three times a day.", "How many times a day does James drink water?", "Three", "Two", "Four", "Five"),
        ("Maria has breakfast at eight and lunch at one.", "When does Maria have lunch?", "At one", "At two", "At twelve", "At three"),
        ("Peter takes a shower in the morning and at night.", "When does Peter take a shower?", "In the morning and at night", "Only in the morning", "Only at night", "After lunch"),
        ("Lucy gets up early on weekdays.", "When does Lucy get up early?", "On weekdays", "At the weekend", "On holidays", "On Sundays"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "travel",
        "context": "announcement",
        "rate": 120.0,
        "suma": 13,
    },
    [
        ("The next train to London arrives at ten.", "Which city is the train going to?", "London", "Oxford", "Manchester", "Leeds"),
        ("This bus goes to the city centre.", "Where does this bus go?", "To the city centre", "To the airport", "To the station", "To the museum"),
        ("The meeting point is next to the coffee shop.", "Where is the meeting point?", "Next to the coffee shop", "Next to the bank", "Next to the hotel", "Next to the station"),
        ("Your hotel is two streets from the beach.", "How far is the hotel from the beach?", "Two streets", "One street", "Three streets", "Five streets"),
        ("The tour starts at the museum at ten.", "Where does the tour start?", "At the museum", "At the station", "At the hotel", "At the park"),
        ("The flight to Rome is delayed by one hour.", "How late is the flight?", "One hour", "Two hours", "Thirty minutes", "Three hours"),
        ("Passengers for Madrid, please go to door five.", "Which door should passengers for Madrid go to?", "Door five", "Door three", "Door two", "Door seven"),
        ("The next bus stop is Green Park.", "What is the next bus stop?", "Green Park", "Central Station", "The Museum", "King Street"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "food",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("David has cereal and juice for breakfast.", "What does David have for breakfast?", "Cereal and juice", "Eggs and toast", "Bread and butter", "Fruit and tea"),
        ("Dad makes pasta on Friday nights.", "When does Dad make pasta?", "On Friday nights", "On Saturday nights", "On Sunday nights", "On Monday nights"),
        ("The soup has carrots and onions.", "What is in the soup?", "Carrots and onions", "Carrots and potatoes", "Tomatoes and onions", "Peas and carrots"),
        ("Sam drinks milk with his dinner.", "What does Sam drink with dinner?", "Milk", "Water", "Juice", "Tea"),
        ("Grandma bakes a cake every Sunday.", "When does Grandma bake a cake?", "Every Sunday", "Every Saturday", "Every Monday", "Every Friday"),
        ("Lunch today is chicken and rice.", "What is for lunch today?", "Chicken and rice", "Fish and rice", "Chicken and salad", "Eggs and rice"),
        ("Anna wants a sandwich with cheese.", "What does Anna want in her sandwich?", "Cheese", "Tomato", "Ham", "Chicken"),
        ("The restaurant opens for dinner at seven.", "When does the restaurant open for dinner?", "At seven", "At six", "At eight", "At five"),
        ("We buy fruit at the market on Saturdays.", "Where do we buy fruit?", "At the market", "At the supermarket", "At the shop", "At the bakery"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "free_time",
        "context": "narrative",
        "rate": 115.0,
        "suma": 11,
    },
    [
        ("Tom plays football with his friends on Saturday.", "Who does Tom play football with?", "His friends", "His brothers", "His classmates", "His dad"),
        ("Lucy reads a book before she sleeps.", "What does Lucy do before she sleeps?", "She reads a book", "She watches TV", "She plays games", "She listens to music"),
        ("We watch a film on Friday evenings.", "When do we watch a film?", "On Friday evenings", "On Saturday evenings", "On Sunday evenings", "On Thursday evenings"),
        ("Ben goes swimming every Sunday morning.", "When does Ben go swimming?", "On Sunday mornings", "On Saturday mornings", "On Sunday evenings", "On Monday mornings"),
        ("Emma plays the piano for thirty minutes.", "How long does Emma play the piano?", "Thirty minutes", "Fifteen minutes", "One hour", "Twenty minutes"),
        ("Dad walks the dog in the park.", "Where does Dad walk the dog?", "In the park", "In the street", "At the beach", "In the forest"),
        ("Anna and her sister play tennis together.", "Who does Anna play tennis with?", "Her sister", "Her brother", "Her mother", "Her friend"),
        ("We meet our friends at the cinema at eight.", "Where do we meet our friends?", "At the cinema", "At the café", "At the park", "At the station"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "education",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("The English class is in room twelve.", "Where is the English class?", "In room twelve", "In room ten", "In room twenty", "In room eleven"),
        ("My teacher gives homework on Mondays.", "When does the teacher give homework?", "On Mondays", "On Tuesdays", "On Fridays", "On Wednesdays"),
        ("Daniel studies English and maths.", "Which subjects does Daniel study?", "English and maths", "English and science", "History and maths", "Maths and music"),
        ("The school bus comes at eight fifteen.", "When does the school bus come?", "At eight fifteen", "At eight", "At seven forty-five", "At eight thirty"),
        ("Anna sits next to her friend in class.", "Who does Anna sit next to?", "Her friend", "Her brother", "The teacher", "Her sister"),
        ("There are twenty students in our class.", "How many students are in the class?", "Twenty", "Twelve", "Thirty", "Fifteen"),
        ("The art class is on Thursday.", "When is the art class?", "On Thursday", "On Tuesday", "On Friday", "On Monday"),
        ("Our first lesson starts at nine.", "What time is the first lesson?", "At nine", "At eight", "At ten", "At half past nine"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "work",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("Mr Brown works in a hospital.", "Where does Mr Brown work?", "In a hospital", "In a school", "In an office", "In a shop"),
        ("Ms Green is a teacher at a primary school.", "What is Ms Green's job?", "A teacher", "A doctor", "A nurse", "A driver"),
        ("Paul starts work at nine every day.", "When does Paul start work?", "At nine", "At eight", "At ten", "At seven"),
        ("Anna has lunch with her colleagues.", "Who does Anna have lunch with?", "Her colleagues", "Her family", "Her friends", "Her boss"),
        ("The manager is in a meeting until three.", "When does the meeting end?", "At three", "At two", "At four", "At one"),
        ("Sam answers the phone at reception.", "What does Sam do at reception?", "He answers the phone", "He makes coffee", "He writes emails", "He cleans the office"),
        ("The post office opens at nine.", "When does the post office open?", "At nine", "At eight", "At ten", "At half past nine"),
        ("Daniel is a driver and works at night.", "When does Daniel work?", "At night", "In the morning", "In the afternoon", "At the weekend"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "weather",
        "context": "message",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("It's freezing outside. Don't forget your gloves!", "What should you remember today?", "Your gloves", "Your umbrella", "Your hat", "Your coat"),
        ("The weather is sunny this afternoon.", "What is the weather this afternoon?", "Sunny", "Rainy", "Windy", "Cloudy"),
        ("It starts to rain at five.", "When does it start to rain?", "At five", "At four", "At six", "At three"),
        ("The snow is very deep this morning.", "What is the weather like this morning?", "Snowy", "Sunny", "Windy", "Foggy"),
        ("Bring an umbrella because it's windy.", "Why should you bring an umbrella?", "Because it's windy", "Because it's sunny", "Because it's hot", "Because it's snowing"),
        ("It's hot today, so wear light clothes.", "What should you wear today?", "Light clothes", "A coat", "A scarf", "Boots"),
        ("The rain stops at noon.", "When does the rain stop?", "At noon", "In the morning", "In the evening", "At night"),
        ("Tomorrow will be warm and dry.", "What will tomorrow's weather be?", "Warm and dry", "Cold and wet", "Hot and windy", "Cool and cloudy"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "shopping",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: Can I help you? B: Yes, I want to buy a birthday card.", "What does the customer want to buy?", "A birthday card", "A pen", "A book", "A bag"),
        ("A: Do you have this shirt in green? B: No, only in blue and red.", "Which colours does the shirt come in?", "Blue and red", "Green and red", "Blue and green", "Black and white"),
        ("A: How much is this hat? B: It's eight pounds.", "How much is the hat?", "Eight pounds", "Six pounds", "Nine pounds", "Ten pounds"),
        ("A: Can I pay by card? B: Yes, of course.", "How can the customer pay?", "By card", "Only in cash", "By phone", "Only online"),
        ("A: Where are the shoes? B: They're at the back of the shop.", "Where are the shoes?", "At the back of the shop", "Near the door", "Next to the till", "On the second floor"),
        ("A: I need a present for my mother. B: How about this scarf?", "What does the customer need?", "A present", "A scarf", "A shirt", "A bag"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "functional",
        "context": "instructions",
        "rate": 120.0,
        "suma": 9,
    },
    [
        ("Turn left at the traffic lights.", "What should you do at the traffic lights?", "Turn left", "Turn right", "Go straight", "Stop"),
        ("Put your name at the top of the page.", "Where should you write your name?", "At the top of the page", "At the bottom of the page", "On the first line", "On the last line"),
        ("The keys are on the table next to the door.", "Where are the keys?", "On the table", "On the chair", "In the drawer", "On the floor"),
        ("Open the window and sit down.", "What should you do first?", "Open the window", "Sit down", "Close the door", "Turn on the light"),
        ("The pharmacy is opposite the bank.", "Where is the pharmacy?", "Opposite the bank", "Next to the bank", "Behind the bank", "Inside the bank"),
        ("Wait here for the doctor.", "Where should you wait?", "Here", "Outside", "In the car", "At home"),
        ("Press the green button to open the door.", "Which button opens the door?", "The green button", "The red button", "The blue button", "The yellow button"),
        ("Take the first street on your right.", "Which street should you take?", "The first street on the right", "The second street on the right", "The first street on the left", "The third street on the right"),
    ],
)

_add(
    {
        "skill": "detail",
        "topic": "sports",
        "context": "narrative",
        "rate": 120.0,
        "suma": 13,
    },
    [
        ("Ben can swim very fast.", "What can Ben do very fast?", "Swim", "Run", "Cycle", "Dance"),
        ("Our team scores two goals in the first half.", "How many goals does our team score?", "Two", "One", "Three", "Four"),
        ("Emma plays tennis twice a week.", "How often does Emma play tennis?", "Twice a week", "Once a week", "Three times a week", "Every day"),
        ("The match starts at three and ends at five.", "When does the match end?", "At five", "At four", "At six", "At three"),
        ("Dad runs five kilometres every morning.", "How far does Dad run?", "Five kilometres", "Three kilometres", "Two kilometres", "Ten kilometres"),
        ("The game is on Saturday at the sports centre.", "Where is the game?", "At the sports centre", "At the park", "At the school", "At the stadium"),
    ],
)

# ---------------------------------------------------------------------------
# GIST — idea principal: anuncios, mensajes, microdiálogos
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "gist",
        "topic": "functional",
        "context": "conversation",
        "rate": 120.0,
        "suma": 9,
    },
    [
        ("A: Excuse me, is there a post office near here? B: Yes, it's on King Street.", "What is the man looking for?", "A post office", "A bank", "A supermarket", "A pharmacy"),
        ("A: Where can I buy stamps? B: At the post office, on High Street.", "What does the man want to buy?", "Stamps", "Bread", "Tickets", "Medicine"),
        ("A: Can you help me? I'm lost. B: Where do you want to go?", "What is the problem?", "The man is lost", "The man is late", "The man is tired", "The man is ill"),
        ("A: Do you know the time? B: Sorry, I don't have a watch.", "What does the man want to know?", "The time", "The way", "The price", "The date"),
        ("A: Is this seat free? B: No, sorry. My friend is sitting here.", "Why can't the man sit there?", "The seat is taken", "The seat is broken", "The seat is wet", "The seat is too small"),
        ("A: I need to send this parcel. B: You can send it over there.", "What does the man want to do?", "Send a parcel", "Buy a ticket", "Find a bank", "Post a letter"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "food",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: What would you like for dinner? B: I'd like chicken with rice.", "What does the woman want for dinner?", "Chicken with rice", "Pasta", "Salad", "Fish"),
        ("A: Do you want a drink? B: Yes, a lemonade, please.", "What does the man want?", "A lemonade", "A coffee", "A tea", "A water"),
        ("A: What do you want to eat? B: A cheese sandwich, please.", "What does the woman want to eat?", "A cheese sandwich", "A chicken sandwich", "A ham sandwich", "A pizza"),
        ("A: Would you like some soup? B: No, thanks. I'd like salad.", "What does the man want?", "Salad", "Soup", "Bread", "Fruit"),
        ("A: What's your favourite fruit? B: I love bananas.", "What fruit does the woman love?", "Bananas", "Apples", "Oranges", "Strawberries"),
        ("A: Are you hungry? B: Yes, I want a burger.", "What does the man want to eat?", "A burger", "A pizza", "A sandwich", "Fish and chips"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "free_time",
        "context": "message",
        "rate": 120.0,
        "suma": 11,
    },
    [
        ("Do you want to come to the cinema with us tonight?", "What is the invitation about?", "Going to the cinema", "Going to a party", "Going to dinner", "Going shopping"),
        ("The football match is on TV at eight. Don't miss it!", "What is the message about?", "A football match", "A film", "The news", "A concert"),
        ("Bring your swimming things. We're going to the pool!", "Where are they going?", "To the pool", "To the beach", "To the park", "To the gym"),
        ("We're having a party on Saturday. Come at seven!", "What is happening on Saturday?", "A party", "A meeting", "A wedding", "A concert"),
        ("I have two tickets for the concert. Do you want one?", "What does the speaker have?", "Tickets for a concert", "Tickets for a film", "Tickets for a match", "Tickets for a train"),
        ("The museum is open until six today.", "What is the message about?", "The museum's opening hours", "A party", "A concert", "A football match"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "travel",
        "context": "announcement",
        "rate": 120.0,
        "suma": 11,
    },
    [
        ("Attention. The train to Oxford is now arriving at platform two.", "What is the announcement about?", "The arrival of a train", "The delay of a flight", "A lost bag", "The weather"),
        ("Please keep your bags with you at all times.", "What should passengers do?", "Keep their bags with them", "Leave their bags here", "Open their bags", "Put bags on the floor"),
        ("The bus to the museum is full. Please wait for the next one.", "What should passengers do?", "Wait for the next bus", "Get off the bus", "Take a taxi", "Walk to the museum"),
        ("The next train is delayed by twenty minutes.", "What is the announcement about?", "A delay", "A cancellation", "A change of platform", "An accident"),
        ("Passengers, please show your tickets at the door.", "What must passengers do?", "Show their tickets", "Buy new tickets", "Sit down", "Open the windows"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "weather",
        "context": "message",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("It's cold and windy outside. Take your coat!", "What is the main message?", "It's cold, take a coat", "It's sunny, go out", "It's raining, take an umbrella", "It's hot, drink water"),
        ("The match is cancelled because of the rain.", "Why is the match cancelled?", "Because of the rain", "Because of the wind", "Because it's too hot", "Because of the snow"),
        ("The sun is out and the sky is blue!", "What is the weather like?", "Sunny", "Cloudy", "Rainy", "Windy"),
        ("Take your umbrella. It's going to rain this evening.", "What should you take?", "An umbrella", "A coat", "A hat", "Boots"),
    ],
)

_add(
    {
        "skill": "gist",
        "topic": "work",
        "context": "message",
        "rate": 120.0,
        "suma": 9,
    },
    [
        ("Please send the report to Mr Jones by Friday.", "What should you do?", "Send the report", "Buy a present", "Call the office", "Book a room"),
        ("The meeting is cancelled. I'll send a new date.", "What is the message about?", "A cancelled meeting", "A new job", "A party", "An appointment"),
        ("Don't forget to turn off the lights when you leave.", "What should you remember?", "Turn off the lights", "Close the windows", "Lock the door", "Call the manager"),
        ("I'm working late tonight. Don't wait for me for dinner.", "Why shouldn't you wait for dinner?", "The speaker is working late", "The speaker is away", "The speaker is ill", "The speaker is on holiday"),
    ],
)

# ---------------------------------------------------------------------------
# ATTITUDE — cómo se siente el hablante
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "attitude",
        "topic": "free_time",
        "context": "message",
        "rate": 120.0,
        "suma": 9,
    },
    [
        ("I'm so happy about the party tonight!", "How does the speaker feel?", "Happy", "Tired", "Worried", "Angry"),
        ("Oh no, the concert is cancelled. What a shame!", "How does the speaker feel?", "Disappointed", "Excited", "Surprised", "Relaxed"),
        ("This is the best day of my life!", "How does the speaker feel?", "Very happy", "Very sad", "Bored", "Nervous"),
        ("I can't wait for the weekend to start!", "How does the speaker feel?", "Excited", "Angry", "Sleepy", "Worried"),
        ("The film was really boring. I fell asleep.", "How did the speaker feel about the film?", "Bored", "Excited", "Frightened", "Amazed"),
        ("What a great game! We played so well!", "How does the speaker feel?", "Proud", "Angry", "Tired", "Shy"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "weather",
        "context": "message",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("Oh no, it's snowing again. What a terrible morning!", "How does the speaker feel?", "Unhappy", "Happy", "Surprised", "Excited"),
        ("Finally, the sun is here. I love this weather!", "How does the speaker feel about the weather?", "Pleased", "Annoyed", "Worried", "Afraid"),
        ("I'm tired of all this snow and cold.", "How does the speaker feel?", "Tired of the cold", "Happy about the snow", "Excited about winter", "Calm"),
        ("This heat is too much. I can't sleep at night.", "How does the speaker feel about the heat?", "Uncomfortable", "Pleased", "Relaxed", "Excited"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "daily_routine",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("I'm so tired. I worked all day.", "How does the speaker feel?", "Tired", "Happy", "Excited", "Angry"),
        ("I'm worried about my exam tomorrow.", "How does the speaker feel?", "Worried", "Relaxed", "Happy", "Bored"),
        ("I love my new job. The people are so nice!", "How does the speaker feel about the new job?", "Happy", "Nervous", "Angry", "Bored"),
        ("I'm angry because my train is late again.", "Why is the speaker angry?", "The train is late", "The train is full", "The train is fast", "The train is cheap"),
        ("I'm nervous about the interview this afternoon.", "What makes the speaker nervous?", "The interview", "The exam", "The meeting", "The trip"),
        ("I feel great after my morning run.", "How does the speaker feel?", "Great", "Tired", "Sad", "Angry"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "sports",
        "context": "narrative",
        "rate": 120.0,
        "suma": 11,
    },
    [
        ("Our team won the final! I can't believe it!", "How does the speaker feel?", "Amazed and happy", "Angry", "Bored", "Sad"),
        ("I was so nervous before the race, but I did my best.", "How did the speaker feel before the race?", "Nervous", "Angry", "Happy", "Relaxed"),
        ("We lost the match. I feel terrible.", "How does the speaker feel?", "Terrible", "Excited", "Proud", "Calm"),
        ("Training is hard, but I love it.", "How does the speaker feel about training?", "They love it", "They hate it", "They're afraid", "They're bored"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "food",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: How's your meal? B: It's delicious, thank you!", "How does the man feel about his meal?", "He loves it", "He hates it", "It's cold", "It's too salty"),
        ("A: Do you like the soup? B: It's a bit cold, sorry.", "How is the soup?", "A bit cold", "Too hot", "Delicious", "Very salty"),
        ("A: Are you happy with your order? B: Not really. The fries are cold.", "How does the woman feel about her order?", "Not happy", "Very happy", "Excited", "Surprised"),
        ("A: What do you think of the cake? B: It's the best cake I've ever had!", "What does the woman think of the cake?", "It's the best cake ever", "It's too sweet", "It's dry", "It's too small"),
    ],
)

_add(
    {
        "skill": "attitude",
        "topic": "shopping",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: Look at this jacket. B: It's beautiful! And it's on sale!", "How does the woman feel about the jacket?", "She loves it", "She hates it", "It's too big", "It's too expensive"),
        ("A: How was the shop? B: Terrible. Everything was too expensive.", "How was the shop?", "Terrible", "Great", "Cheap", "Interesting"),
        ("A: Can I help you? B: No thanks, I'm just looking.", "How does the customer feel?", "Just looking", "Ready to buy", "In a hurry", "Angry"),
        ("A: I love this shop. The prices are very good.", "How does the speaker feel about the shop?", "They love it", "They hate it", "They're bored", "They're surprised"),
    ],
)

# ---------------------------------------------------------------------------
# SPEAKER_INTENTION — qué quiere/ofrece el hablante
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "speaker_intention",
        "topic": "food",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: Would you like some coffee? B: No thanks, I'd like some tea.", "What does the woman want?", "Tea", "Coffee", "Juice", "Water"),
        ("A: Can I get you anything? B: Yes, a glass of water, please.", "What does the man want?", "A glass of water", "A cup of tea", "A lemonade", "A coffee"),
        ("A: Do you want more rice? B: Yes, please. It's very good.", "What does the woman want?", "More rice", "More bread", "More salad", "Nothing"),
        ("A: What would you like to drink? B: Just water for me, please.", "What does the woman want to drink?", "Water", "Tea", "Coffee", "Juice"),
        ("A: Can I order a pizza, please? B: Of course. What do you want on it?", "What does the man want to order?", "A pizza", "A burger", "Pasta", "A salad"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "shopping",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: Can I help you? B: Yes, I'm looking for a scarf.", "What does the customer want?", "A scarf", "A pair of shoes", "A shirt", "A hat"),
        ("A: Excuse me, do you sell batteries? B: Yes, they're over there.", "What does the customer want to buy?", "Batteries", "Bread", "Medicine", "Newspapers"),
        ("A: I'd like to return this shirt. B: Do you have the receipt?", "What does the customer want to do?", "Return a shirt", "Buy a shirt", "Try on a shirt", "Pay for a shirt"),
        ("A: Could you wrap this as a present, please? B: Of course.", "What does the customer want?", "A present for a friend", "A new bag", "A bigger size", "A receipt"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "travel",
        "context": "conversation",
        "rate": 120.0,
        "suma": 11,
    },
    [
        ("A: One ticket to London, please. B: Single or return?", "What does the man want?", "A ticket to London", "A ticket to Paris", "A map", "A timetable"),
        ("A: Can I change my ticket to tomorrow? B: Let me check for you.", "What does the passenger want?", "To change the ticket date", "To get a refund", "A window seat", "A map"),
        ("A: How do I get to the airport? B: Take the number ten bus.", "What does the woman want to know?", "How to get to the airport", "The price of the bus", "Where the bus stop is", "When the bus leaves"),
        ("A: Could you call me a taxi? B: Sure, it will be here soon.", "What does the man want?", "A taxi", "A bus", "A train", "A map"),
        ("A: Where is the luggage office? B: It's on the ground floor.", "What is the woman looking for?", "The luggage office", "The toilets", "The ticket office", "The café"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "work",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: Good morning. I have an appointment with Dr Lee.", "Why is the man at the office?", "He has an appointment", "He wants a job", "He is lost", "He wants a coffee"),
        ("A: Can you help me with this computer? B: Let me look at it.", "What does the woman want?", "Help with the computer", "A new computer", "A coffee", "A rest"),
        ("A: I'd like to speak to the manager, please.", "Who does the man want to speak to?", "The manager", "The doctor", "The teacher", "The driver"),
        ("A: Could you send me the price list by email? B: Of course.", "What does the woman want?", "The price list by email", "A new phone", "A meeting", "A receipt"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "daily_routine",
        "context": "message",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("Please call me when you get home.", "What does the speaker want you to do?", "Call them", "Visit them", "Email them", "Wait for them"),
        ("Can you buy some milk on your way home?", "What does the speaker want?", "Some milk", "Some bread", "Some eggs", "Some fruit"),
        ("Don't wait for me. I'll take the bus.", "What should you do?", "Not wait for the speaker", "Take the bus together", "Call a taxi", "Wait at the station"),
        ("Please feed the cat while I'm away.", "What does the speaker want you to do?", "Feed the cat", "Walk the dog", "Water the plants", "Clean the house"),
    ],
)

_add(
    {
        "skill": "speaker_intention",
        "topic": "functional",
        "context": "conversation",
        "rate": 120.0,
        "suma": 11,
    },
    [
        ("A: Can I use your phone? Mine is dead. B: Of course.", "What does the man want?", "To use the phone", "To charge his phone", "To buy a phone", "To make a call at home"),
        ("A: Could you open the window? It's hot in here.", "What does the woman want?", "The window open", "The door open", "Some water", "A fan"),
        ("A: Excuse me, can I sit here? B: Sorry, it's taken.", "What does the man want to do?", "Sit there", "Stand there", "Leave", "Open a window"),
        ("A: Can you help me carry this box? B: Yes, of course.", "What does the woman want?", "Help carrying a box", "A new box", "A bag", "Some water"),
    ],
)

# ---------------------------------------------------------------------------
# VOCABULARY — significado de la palabra oída
# ---------------------------------------------------------------------------
_add(
    {
        "skill": "vocabulary",
        "topic": "daily_routine",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("Dan goes to school at eight every morning.", "Which word means 'todas las mañanas'?", "every morning", "every evening", "every night", "every day"),
        ("Anna wakes up at seven every morning.", "Which word means 'se despierta'?", "wakes up", "gets up", "goes out", "lies down"),
        ("Tom eats breakfast at home.", "Which word means 'desayuno'?", "breakfast", "lunch", "dinner", "snack"),
        ("Dad drives to work every day.", "Which word means 'conduce'?", "drives", "walks", "rides", "flies"),
        ("Lucy helps her mother in the kitchen.", "Which word means 'ayuda'?", "helps", "watches", "hears", "leaves"),
        ("Ben washes his car on Sundays.", "Which word means 'lava'?", "washes", "dries", "paints", "cleans"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "food",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("The soup is hot. Wait a minute!", "Which word means 'caliente'?", "hot", "cold", "warm", "cool"),
        ("I buy fresh bread at the bakery.", "Which word means 'fresco'?", "fresh", "old", "dry", "soft"),
        ("This apple is sweet and juicy.", "Which word means 'dulce'?", "sweet", "sour", "bitter", "salty"),
        ("The cake is on the table. Please cut it.", "Which word means 'cortar'?", "cut", "eat", "cook", "buy"),
        ("We need salt for the potatoes.", "Which word means 'sal'?", "salt", "sugar", "oil", "pepper"),
        ("The waiter brings us the menu.", "Which word means 'camarero'?", "waiter", "cook", "driver", "teacher"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "travel",
        "context": "instructions",
        "rate": 120.0,
        "suma": 11,
    },
    [
        ("Please keep your seat belt on during the flight.", "Which word means 'cinturón de seguridad'?", "seat belt", "window", "door", "seat"),
        ("The train leaves from this platform.", "Which word means 'andén'?", "platform", "ticket", "station", "track"),
        ("Show your passport at the door, please.", "Which word means 'pasaporte'?", "passport", "ticket", "boarding pass", "bag"),
        ("The bus is very full today.", "Which word means 'lleno'?", "full", "empty", "slow", "late"),
        ("Turn left at the corner, please.", "Which word means 'esquina'?", "corner", "street", "road", "bridge"),
        ("The driver stops at every station.", "Which word means 'se detiene'?", "stops", "starts", "turns", "waits"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "education",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("Please answer the questions on page two.", "Which word means 'responder'?", "answer", "ask", "read", "write"),
        ("The teacher writes on the board.", "Which word means 'pizarra'?", "board", "book", "paper", "desk"),
        ("Learn these words for tomorrow.", "Which word means 'aprende'?", "learn", "forget", "read", "copy"),
        ("Open your books at page ten.", "Which word means 'abrid'?", "open", "close", "turn", "put"),
        ("The classroom is very quiet today.", "Which word means 'silencio' / 'tranquilo'?", "quiet", "noisy", "small", "empty"),
        ("Bring your pencils to class.", "Which word means 'traed'?", "bring", "take", "buy", "find"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "weather",
        "context": "message",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("Take an umbrella. It's raining outside.", "Which word means 'lloviendo'?", "raining", "snowing", "shining", "blowing"),
        ("The sky is cloudy this morning.", "Which word means 'nublado'?", "cloudy", "sunny", "clear", "grey"),
        ("The wind is very strong today.", "Which word means 'viento'?", "wind", "rain", "snow", "cloud"),
        ("The ice on the road is dangerous.", "Which word means 'hielo'?", "ice", "snow", "rain", "fog"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "shopping",
        "context": "conversation",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("A: Do you have this in a bigger size? B: Yes, here you are.", "Which word means 'talla' / 'tamaño'?", "size", "price", "colour", "style"),
        ("A: This bag is very cheap! B: Yes, it's on sale.", "Which word means 'barato'?", "cheap", "expensive", "new", "old"),
        ("A: Can I pay with cash? B: Sure.", "Which word means 'efectivo'?", "cash", "card", "money", "change"),
        ("A: Where is the changing room? B: It's over there.", "Which word means 'probador'?", "changing room", "shop", "door", "counter"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "sports",
        "context": "narrative",
        "rate": 120.0,
        "suma": 13,
    },
    [
        ("Ben swims very well. He trains three times a week.", "Which word means 'entrena'?", "trains", "plays", "sleeps", "eats"),
        ("Our team wins the match.", "Which word means 'gana'?", "wins", "loses", "starts", "stops"),
        ("The players run onto the field.", "Which word means 'campo' / 'pista'?", "field", "room", "street", "pool"),
        ("She kicks the ball to her friend.", "Which word means 'patea'?", "kicks", "throws", "catches", "hits"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "functional",
        "context": "instructions",
        "rate": 120.0,
        "suma": 9,
    },
    [
        ("Close the window. Then open the door.", "Which word means 'después'?", "then", "first", "now", "soon"),
        ("Please close the door behind you.", "Which word means 'detrás de'?", "behind", "in front of", "next to", "under"),
        ("Write your address on this form.", "Which word means 'dirección'?", "address", "name", "age", "phone"),
        ("This room is free. You can use it.", "Which word means 'libre' / 'disponible'?", "free", "busy", "closed", "full"),
        ("Press the button and wait.", "Which word means 'esperar'?", "wait", "run", "leave", "listen"),
        ("The sign says 'Exit' in big letters.", "Which word means 'salida'?", "Exit", "Entrance", "Window", "Door"),
    ],
)

_add(
    {
        "skill": "vocabulary",
        "topic": "free_time",
        "context": "narrative",
        "rate": 115.0,
        "suma": 9,
    },
    [
        ("We listen to music in the car.", "Which word means 'escuchamos'?", "listen", "hear", "watch", "play"),
        ("Tom plays the guitar at home.", "Which word means 'guitarra'?", "guitar", "piano", "drums", "violin"),
        ("I read a funny book at the weekend.", "Which word means 'divertido'?", "funny", "sad", "long", "easy"),
        ("We sing songs around the fire.", "Which word means 'cantamos'?", "sing", "dance", "talk", "shout"),
        ("She draws a picture of her house.", "Which word means 'dibuja'?", "draws", "paints", "writes", "colours"),
        ("We dance at the party.", "Which word means 'bailar'?", "dance", "walk", "run", "jump"),
    ],
)

# Rebalance de dificultad dentro de banda: grupos con dos cláusulas, cifras
# dobles o varios detalles suben a scalar 2 (suma 13) para que la ruta A1 no sea
# plana en dificultad 1.
_REBALANCE_A1: dict[tuple[str, str], int] = {
    ("gist", "travel"): 13,
    ("detail", "daily_routine"): 13,
    ("vocabulary", "travel"): 13,
    ("speaker_intention", "travel"): 13,
    ("numbers", "travel"): 13,
}
for _f in FRAMES_A1:
    _tgt = _REBALANCE_A1.get((_f["skill"], _f["topic"]))
    if _tgt:
        _f["difficulty_vector"] = _vector(
            _tgt, _f["difficulty_vector"]["speaker_count"]
        )

# ---------------------------------------------------------------------------
# Guards de autoría: bandas auditadas A1 (14 palabras, scalar 1..2).
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    from collections import Counter

    print("A1 frames:", len(FRAMES_A1))
    print("Por skill:", dict(Counter(f["skill"] for f in FRAMES_A1)))
    print("Por topic:", dict(Counter(f["topic"] for f in FRAMES_A1)))
