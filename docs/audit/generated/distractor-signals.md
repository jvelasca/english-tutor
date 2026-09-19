# Señales de distractor inferible (V3.75.1 · pausa pedagógica)

> Generado por `python -m scripts.audit_dossier distractor-signals`.
> Solo lectura. Heurísticas DECLARADAS y deterministas: marcan ítems que
> permiten acertar por forma o por eco léxico, no ítems mal escritos.
> La parte cualitativa la cierra la muestra determinista.

## Definición de las señales

- `prompt_keyword_echo`: El enunciado comparte una palabra de contenido con la opción correcta y con ninguna otra: la correcta se puede emparejar sin comprender.
- `shape_outlier`: La opción correcta es el outlier de longitud: se desvía de la mediana de los distractores en >= 50 % y esa desviación es la mayor del ítem.
- `quantity_literal`: El enunciado pide una cantidad o un momento (how many, what time, when...) y solo la opción correcta contiene una cifra, un número escrito o un día de la semana.

## Recuento por banco

| Banco | N | con señal | prompt_keyword_echo | shape_outlier | quantity_literal |
|---|---|---|---|---|---|
| checks_curriculum | 368 | 79 | 22 (6.0%) | 59 (16.0%) | 0 (0.0%) |
| corpus_listening | 490 | 104 | 2 (0.4%) | 103 (21.0%) | 0 (0.0%) |
| exams | 22 | 7 | 3 (13.6%) | 6 (27.3%) | 0 (0.0%) |
| placement | 24 | 6 | 2 (8.3%) | 4 (16.7%) | 1 (4.2%) |

## Muestra determinista (semilla fija) para revisión cualitativa

### checks_curriculum

- `a1-m05-u01-l01-o03-c01` [A1] correcta=2 señales=prompt_keyword_echo — Listen: 'Maria eats an apple every day for breakfast.' What does Maria eat for breakfast?
  - 0:A banana; 1:Bread; 2:An apple; 3:Eggs
- `a1-m06-u01-l01-o03-c02` [A1] correcta=1 señales=prompt_keyword_echo — Listen: 'I'm looking for a jacket.' What does the customer want?
  - 0:A drink; 1:A jacket; 2:A ticket; 3:A book
- `a2-m02-u01-l01-o03-c03` [A2] correcta=0 señales=shape_outlier — Which phrase means 'más caro'?
  - 0:more expensive; 1:cheaper; 2:bigger
- `b1-m03-u01-l01-o17-c02` [B1] correcta=1 señales=shape_outlier — Which phrase asks someone to continue their story?
  - 0:I see.; 1:What happened next?; 2:That's it.
- `c1-m01-u01-l01-o03-c02` [C1] correcta=1 señales=prompt_keyword_echo — You hear: 'Never have I seen such dedication.' What is the speaker stressing?
  - 0:That they were not dedicated; 1:How unusual the dedication is; 2:A past routine

### corpus_listening

- `c020` [A2] correcta=0 señales=shape_outlier — What did B think about the party?
  - 0:It was enjoyable but crowded; 1:It was boring; 2:It was too short; 3:It was cancelled
- `c097` [B2] correcta=0 señales=shape_outlier — What does B suggest?
  - 0:Checking with the kitchen; 1:Leaving the restaurant; 2:Ordering more; 3:Complaining
- `c152` [A1] correcta=0 señales=shape_outlier — What does the customer want to buy?
  - 0:A birthday card; 1:A bag; 2:A book; 3:A pen
- `c205` [A1] correcta=3 señales=shape_outlier — When does the train arrive?
  - 0:At nine twenty; 1:At eight; 2:At nine; 3:At eight twenty
- `c388` [A2] correcta=1 señales=shape_outlier — What does the woman want?
  - 0:A day off; 1:The minutes sent to everyone; 2:A new schedule; 3:A shorter meeting

### exams

- `a1f-03` [a1] correcta=1 señales=shape_outlier — Complete: 'There ___ two bedrooms in my house.'
  - 0:is; 1:are; 2:be
- `a1f-08` [a1] correcta=1 señales=prompt_keyword_echo — Read: 'I get up at seven and I have breakfast at eight.' What does he do at eight?
  - 0:Gets up; 1:Has breakfast; 2:Goes to work
- `b1f-06` [b1] correcta=0 señales=prompt_keyword_echo, shape_outlier — Which phrase introduces a personal opinion?
  - 0:In my opinion; 1:By the way; 2:At last
- `b1f-07` [b1] correcta=0 señales=shape_outlier — Read: 'Although the journey was long, they enjoyed every minute of it.' What does the sentence mean?
  - 0:They enjoyed the journey despite its length.; 1:They hated the journey.; 2:The journey was short.
- `b1f-08` [b1] correcta=0 señales=shape_outlier — Read: 'She had never seen the ocean until she moved to the coast.' What happened?
  - 0:She saw the ocean for the first time after moving.; 1:She saw the ocean before moving.; 2:She never moved.

### placement

- `pl-04` [placement] correcta=1 señales=prompt_keyword_echo, quantity_literal — Read: 'I go to work at eight every day.' When does he go to work?
  - 0:At night; 1:At eight; 2:At noon
- `pl-10` [placement] correcta=1 señales=shape_outlier — Which word is a synonym of 'ubiquitous'?
  - 0:rare; 1:everywhere; 2:hidden
- `pl-12` [placement] correcta=1 señales=shape_outlier — Read: 'His argument, though subtle, was ultimately compelling.' What is the tone?
  - 0:Negative; 1:Neutral-positive; 2:Confused
- `pl-13` [placement] correcta=0 señales=prompt_keyword_echo — You hear: 'She went to the market to buy some bread.' Where did she go?
  - 0:To the market; 1:To the park; 2:To the bank
- `pl-18` [placement] correcta=1 señales=shape_outlier — Which opener is most idiomatic for disagreeing politely in a formal meeting?
  - 0:You're totally wrong.; 1:I see your point, but I'd argue that...; 2:Nah, that's dumb.
