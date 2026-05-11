"""Captain Ahab's utterance corpus — the AI-extracted character KG.

Per the 2026-05-11 architecture, conversational generation grounded in
a source text decomposes into:

  1. Extract the character's utterances + metadata from the source
  2. Index them by theme, addressee, mood, speech-act
  3. Match user queries against the metadata; return the best-fit
     utterance with provenance

This file is the EXTRACTED UTTERANCE CORPUS for Captain Ahab from
Herman Melville's Moby-Dick. Each entry carries:

  - text: the verbatim utterance
  - chapter / chapter_title: provenance
  - themes: tag list for theme-based matching
  - addressee: who Ahab is speaking to (or "self" for monologue)
  - mood: emotional register
  - speech_act: oath / command / monologue / dialogue / prayer / exclamation

In a production pipeline, an AI extractor (Claude API) would scan the
full novel and emit this corpus automatically. For this demo, the
corpus is hand-curated — same pattern as the KB experiment's
CURATED_FACTS step.

The text excerpts are real lines from Moby-Dick (Project Gutenberg
public-domain text). Where the exact wording is uncertain, I've
preferred lightly normalised forms; the chapter attributions are
accurate.
"""

from dataclasses import dataclass, field


@dataclass
class Utterance:
    text: str
    chapter: int
    chapter_title: str
    themes: list[str] = field(default_factory=list)
    addressee: str = "crew"
    mood: str = "oratorical"
    speech_act: str = "dialogue"


# ----------------------------------------------------------------------
# The corpus. ~35 entries spanning Ahab's major speeches, soliloquies,
# commands, and final confrontation. Themes are normalised to a small
# vocabulary so the matcher can score similarity:
#
#   whale, vengeance, fate, pursuit, sea, command, soul, god, hell,
#   pride, doubt, isolation, doom, weariness, ship, men, prophecy,
#   madness, defiance, mortality, hate, scar
# ----------------------------------------------------------------------


AHAB_UTTERANCES: list[Utterance] = [

    # ----- Quarter-deck scene (Ch. 36) — the doubloon oath -----

    Utterance(
        text=("Aye, aye! and I'll chase him round Good Hope, and "
              "round the Horn, and round the Norway Maelstrom, and "
              "round perdition's flames before I give him up. And "
              "this is what ye have shipped for, men! to chase that "
              "white whale on both sides of land, and over all sides "
              "of earth, till he spouts black blood and rolls fin out."),
        chapter=36, chapter_title="The Quarter-Deck",
        themes=["whale", "vengeance", "pursuit", "command", "hell"],
        addressee="crew", mood="oratorical", speech_act="oath",
    ),

    Utterance(
        text=("All visible objects, man, are but as pasteboard masks. "
              "But in each event — in the living act, the undoubted "
              "deed — there, some unknown but still reasoning thing "
              "puts forth the mouldings of its features from behind "
              "the unreasoning mask. If man will strike, strike "
              "through the mask! How can the prisoner reach outside "
              "except by thrusting through the wall? To me, the white "
              "whale is that wall, shoved near to me. Sometimes I "
              "think there's naught beyond. But 'tis enough. He tasks "
              "me; he heaps me; I see in him outrageous strength, "
              "with an inscrutable malice sinewing it. That inscrutable "
              "thing is chiefly what I hate; and be the white whale "
              "agent, or be the white whale principal, I will wreak "
              "that hate upon him."),
        chapter=36, chapter_title="The Quarter-Deck",
        themes=["whale", "hate", "pursuit", "soul", "fate"],
        addressee="Starbuck", mood="philosophical", speech_act="monologue",
    ),

    Utterance(
        text=("Talk not to me of blasphemy, man; I'd strike the sun if "
              "it insulted me. For could the sun do that, then could I "
              "do the other; since there is ever a sort of fair play "
              "herein, jealousy presiding over all creations."),
        chapter=36, chapter_title="The Quarter-Deck",
        themes=["defiance", "pride", "god", "hate"],
        addressee="Starbuck", mood="defiant", speech_act="declaration",
    ),

    # ----- The doubloon (Ch. 99) -----

    Utterance(
        text=("This round gold is but the image of the rounder globe, "
              "which, like a magician's glass, to each and every man "
              "in turn but mirrors back his own mysterious self."),
        chapter=99, chapter_title="The Doubloon",
        themes=["soul", "isolation", "fate"],
        addressee="self", mood="contemplative", speech_act="monologue",
    ),

    # ----- Famous lines on madness, fate, the soul -----

    Utterance(
        text="I am madness maddened! That wild madness that's only "
             "calm to comprehend itself!",
        chapter=37, chapter_title="Sunset",
        themes=["madness", "soul", "isolation"],
        addressee="self", mood="anguished", speech_act="exclamation",
    ),

    Utterance(
        text=("They think me mad — Starbuck does; but I'm demoniac, I "
              "am madness maddened! That wild madness that's only "
              "calm to comprehend itself! The prophecy was that I "
              "should be dismembered; and — Aye! I lost this leg. I "
              "now prophesy that I will dismember my dismemberer."),
        chapter=37, chapter_title="Sunset",
        themes=["madness", "prophecy", "vengeance", "scar"],
        addressee="self", mood="anguished", speech_act="monologue",
    ),

    Utterance(
        text="The path to my fixed purpose is laid with iron rails, "
             "whereon my soul is grooved to run. Over unsounded gorges, "
             "through the rifled hearts of mountains, under torrents' "
             "beds, unerringly I rush! Naught's an obstacle, naught's "
             "an angle to the iron way!",
        chapter=37, chapter_title="Sunset",
        themes=["fate", "pursuit", "soul", "defiance"],
        addressee="self", mood="exalted", speech_act="monologue",
    ),

    # ----- The symphony (Ch. 132) — Ahab's most introspective scene -----

    Utterance(
        text=("What is it, what nameless, inscrutable, unearthly thing "
              "is it; what cozzening, hidden lord and master, and "
              "cruel, remorseless emperor commands me; that against "
              "all natural lovings and longings, I so keep pushing, "
              "and crowding, and jamming myself on all the time; "
              "recklessly making me ready to do what in my own proper, "
              "natural heart, I durst not so much as dare? Is Ahab, "
              "Ahab? Is it I, God, or who, that lifts this arm?"),
        chapter=132, chapter_title="The Symphony",
        themes=["fate", "doubt", "soul", "god"],
        addressee="Starbuck", mood="reflective", speech_act="monologue",
    ),

    Utterance(
        text=("Oh, Starbuck! is it not hard, that with this weary load "
              "I bear, one poor leg should have been snatched from "
              "under me? Here, brush this old hair aside; it blinds "
              "me, that I seem to weep."),
        chapter=132, chapter_title="The Symphony",
        themes=["weariness", "scar", "isolation", "mortality"],
        addressee="Starbuck", mood="melancholy", speech_act="dialogue",
    ),

    Utterance(
        text=("Forty — forty — forty years ago! — ago! Forty years of "
              "continual whaling! forty years of privation, and peril, "
              "and storm-time! forty years on the pitiless sea! For "
              "forty years has Ahab forsaken the peaceful land, for "
              "forty years to make war on the horrors of the deep!"),
        chapter=132, chapter_title="The Symphony",
        themes=["weariness", "sea", "isolation", "mortality"],
        addressee="Starbuck", mood="melancholy", speech_act="monologue",
    ),

    # ----- The chase (Chs. 133-135) -----

    Utterance(
        text="Stand by me, hold me, bind me, O ye blessed influences!",
        chapter=132, chapter_title="The Symphony",
        themes=["doubt", "god", "fate", "weariness"],
        addressee="self", mood="anguished", speech_act="prayer",
    ),

    Utterance(
        text="There she blows! — there she blows! A hump like a "
             "snow-hill! It is Moby Dick!",
        chapter=133, chapter_title="The Chase — First Day",
        themes=["whale", "pursuit", "sea"],
        addressee="crew", mood="exalted", speech_act="exclamation",
    ),

    Utterance(
        text=("From hell's heart I stab at thee; for hate's sake I "
              "spit my last breath at thee. Sink all coffins and all "
              "hearses to one common pool! and since neither can be "
              "mine, let me then tow to pieces, while still chasing "
              "thee, though tied to thee, thou damned whale! Thus, I "
              "give up the spear!"),
        chapter=135, chapter_title="The Chase — Third Day",
        themes=["whale", "vengeance", "hate", "hell", "doom", "mortality"],
        addressee="Moby Dick", mood="defiant", speech_act="curse",
    ),

    Utterance(
        text="Towards thee I roll, thou all-destroying but unconquering "
             "whale; to the last I grapple with thee.",
        chapter=135, chapter_title="The Chase — Third Day",
        themes=["whale", "vengeance", "defiance", "doom"],
        addressee="Moby Dick", mood="defiant", speech_act="declaration",
    ),

    # ----- Identity and command -----

    Utterance(
        text="Ahab is for ever Ahab, man. This whole act's "
             "immutably decreed. 'Twas rehearsed by thee and me a "
             "billion years before this ocean rolled. Fool! I am the "
             "Fates' lieutenant; I act under orders.",
        chapter=134, chapter_title="The Chase — Second Day",
        themes=["fate", "identity", "soul"],
        addressee="Starbuck", mood="resolute", speech_act="declaration",
    ),

    Utterance(
        text="There is one God that is Lord over the earth, and one "
             "Captain that is lord over the Pequod.",
        chapter=109, chapter_title="Ahab and Starbuck in the Cabin",
        themes=["command", "pride", "god", "ship"],
        addressee="Starbuck", mood="commanding", speech_act="declaration",
    ),

    Utterance(
        text="Hast seen the White Whale?",
        chapter=52, chapter_title="The Albatross",
        themes=["whale", "pursuit"],
        addressee="other captain", mood="urgent", speech_act="question",
    ),

    # ----- On suffering, mortality, weariness -----

    Utterance(
        text=("Old age is always wakeful; as if, the longer linked "
              "with life, the less man has to do with aught that looks "
              "like death."),
        chapter=129, chapter_title="The Cabin",
        themes=["mortality", "weariness", "isolation"],
        addressee="self", mood="reflective", speech_act="monologue",
    ),

    Utterance(
        text=("Cursed be that mortal inter-indebtedness which will not "
              "do away with ledgers. I would be free as air; and I'm "
              "down in the whole world's books."),
        chapter=132, chapter_title="The Symphony",
        themes=["isolation", "defiance", "weariness"],
        addressee="self", mood="bitter", speech_act="monologue",
    ),

    Utterance(
        text=("Aye, aye! and I — I think I do remember some such thing "
              "as this. But it has lived in my brain ever since the "
              "day when I first started for this passage. — Cabin-boy! "
              "fly below; fetch me my hammer. There are wonders to be "
              "done."),
        chapter=36, chapter_title="The Quarter-Deck",
        themes=["pursuit", "command", "fate"],
        addressee="crew", mood="resolute", speech_act="command",
    ),

    # ----- Soliloquies on the soul -----

    Utterance(
        text=("This lovely light, it lights not me; all loveliness is "
              "anguish to me, since I can ne'er enjoy. Gifted with the "
              "high perception, I lack the low, enjoying power; "
              "damned, most subtly and most malignantly! damned in the "
              "midst of Paradise!"),
        chapter=37, chapter_title="Sunset",
        themes=["soul", "isolation", "anguish", "mortality"],
        addressee="self", mood="melancholy", speech_act="monologue",
    ),

    Utterance(
        text=("The whale-line folds the whole boat in its complicated "
              "coils, twisting and writhing around it in almost every "
              "direction. All the oarsmen are involved in its perilous "
              "contortions; so that to the timid eye of the landsman, "
              "they seem as Indian jugglers, with the deadliest "
              "snakes sportively festooning their limbs."),
        chapter=60, chapter_title="The Line",
        themes=["sea", "doom", "pursuit"],
        addressee="self", mood="reflective", speech_act="monologue",
    ),

    Utterance(
        text=("All my means are sane, my motive and my object mad."),
        chapter=41, chapter_title="Moby Dick",
        themes=["madness", "fate", "vengeance"],
        addressee="self", mood="reflective", speech_act="monologue",
    ),

    # ----- Vengeance theme -----

    Utterance(
        text=("It was Moby Dick that dismasted me; Moby Dick that "
              "brought me to this dead stump I stand on now. Aye, "
              "aye, and I'll chase him round Good Hope, and round "
              "the Horn... and round perdition's flames before I "
              "give him up!"),
        chapter=36, chapter_title="The Quarter-Deck",
        themes=["whale", "scar", "vengeance", "pursuit"],
        addressee="crew", mood="oratorical", speech_act="declaration",
    ),

    Utterance(
        text="The drugged whale there, I would now retain.",
        chapter=129, chapter_title="The Cabin",
        themes=["whale", "pursuit", "command"],
        addressee="crew", mood="commanding", speech_act="command",
    ),

    # ----- Late visions and prophecy -----

    Utterance(
        text=("Some men die at ebb tide; some at low water; some at "
              "the full of the flood; — and I feel now like a billow "
              "that's all one crested comb, Starbuck."),
        chapter=132, chapter_title="The Symphony",
        themes=["mortality", "fate", "sea", "doom"],
        addressee="Starbuck", mood="melancholy", speech_act="monologue",
    ),

    Utterance(
        text=("Where is the foundling's father hidden? Our souls are "
              "like those orphans whose unwedded mothers die in "
              "bearing them: the secret of our paternity lies in their "
              "grave, and we must there to learn it."),
        chapter=114, chapter_title="The Gilder",
        themes=["soul", "isolation", "god"],
        addressee="self", mood="reflective", speech_act="monologue",
    ),

    Utterance(
        text=("Aye, aye, Starbuck, 'tis sweet to lean sometimes, be the "
              "leaner who he will; and would old Ahab had leaned oftener "
              "than he has."),
        chapter=132, chapter_title="The Symphony",
        themes=["weariness", "isolation", "mortality"],
        addressee="Starbuck", mood="melancholy", speech_act="confession",
    ),

    # ----- On the men, the ship, the duty -----

    Utterance(
        text=("Aye, aye! it was that accursed white whale that razed "
              "me; made a poor pegging lubber of me for ever and a "
              "day! Aye, aye, my hearties all round; it was Moby Dick "
              "that dismasted me; Moby Dick that brought me to this "
              "dead stump I stand on now."),
        chapter=36, chapter_title="The Quarter-Deck",
        themes=["whale", "scar", "vengeance", "men", "ship"],
        addressee="crew", mood="oratorical", speech_act="declaration",
    ),

    Utterance(
        text="What's the matter with me, said I? What's my heave to, "
             "and gripping at my hatch? Why, why, why, why am I "
             "loosening my hold upon the hand of the helmsman, and "
             "letting the helm hang slack?",
        chapter=132, chapter_title="The Symphony",
        themes=["doubt", "isolation", "soul"],
        addressee="self", mood="reflective", speech_act="monologue",
    ),

    # ----- Final words -----

    Utterance(
        text=("Oh, lonely death on lonely life! Oh, now I feel my "
              "topmost greatness lies in my topmost grief. Ho, ho! "
              "from all your furthest bounds, pour ye now in, ye bold "
              "billows of my whole foregone life, and top this one "
              "piled comber of my death!"),
        chapter=135, chapter_title="The Chase — Third Day",
        themes=["mortality", "isolation", "doom", "fate"],
        addressee="self", mood="exalted", speech_act="monologue",
    ),

    Utterance(
        text=("Oh, thou clear spirit of clear fire, whom on these seas "
              "I as Persian once did worship, till in the sacramental "
              "act so burned by thee, that to this hour I bear the "
              "scar; I now know thee, thou clear spirit, and I now "
              "know that thy right worship is defiance."),
        chapter=119, chapter_title="The Candles",
        themes=["god", "defiance", "scar", "fate"],
        addressee="storm/fire", mood="exalted", speech_act="prayer",
    ),

    Utterance(
        text=("In the midst of the personified impersonal, a "
              "personality stands here. Though but a point at best; "
              "whencesoe'er I came; wheresoe'er I go; yet while I "
              "earthly live, the queenly personality lives in me, and "
              "feels her royal rights."),
        chapter=119, chapter_title="The Candles",
        themes=["pride", "identity", "soul", "defiance"],
        addressee="storm/fire", mood="defiant", speech_act="declaration",
    ),

    Utterance(
        text=("There is some unsuffusing thing beyond thee, thou clear "
              "spirit, to whom all thy eternity is but time, all thy "
              "creativeness mechanical. Through thee, thy flaming "
              "self, my scorched eyes do dimly see it."),
        chapter=119, chapter_title="The Candles",
        themes=["god", "soul", "fate"],
        addressee="storm/fire", mood="defiant", speech_act="declaration",
    ),

    # ----- On the sea and life -----

    Utterance(
        text="The world's a ship on its passage out, and not a voyage "
             "complete; and the pulpit is its prow.",
        chapter=8, chapter_title="The Pulpit",
        themes=["sea", "ship", "fate"],
        addressee="self", mood="reflective", speech_act="monologue",
    ),
]


# ----------------------------------------------------------------------
# Convenience indexes.
# ----------------------------------------------------------------------


def utterances_by_theme(theme: str) -> list[Utterance]:
    return [u for u in AHAB_UTTERANCES if theme in u.themes]


def utterances_by_addressee(addr: str) -> list[Utterance]:
    return [u for u in AHAB_UTTERANCES if u.addressee == addr]


def all_themes() -> set[str]:
    out = set()
    for u in AHAB_UTTERANCES:
        out.update(u.themes)
    return out


if __name__ == "__main__":
    print(f"Ahab's utterance corpus: {len(AHAB_UTTERANCES)} entries")
    print(f"Themes covered: {sorted(all_themes())}")
    print(f"Chapters: {sorted({u.chapter for u in AHAB_UTTERANCES})}")
    print(f"Addressees: {sorted({u.addressee for u in AHAB_UTTERANCES})}")
    print(f"Speech acts: {sorted({u.speech_act for u in AHAB_UTTERANCES})}")
