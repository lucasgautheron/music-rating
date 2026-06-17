"""PsyNet experiment where participants rate music clips from 1 to 8."""

# pylint: disable=missing-class-docstring,missing-function-docstring

import csv
from pathlib import Path
from tkinter import N

from dominate import tags
from markupsafe import Markup

import psynet.experiment
from psynet.asset import Asset, asset  # noqa
from psynet.bot import Bot
from psynet.modular_page import ModularPage, RatingControl
from psynet.page import InfoPage, SuccessfulEndPage, VolumeCalibration
from psynet.participant import Participant
from psynet.prescreen import AudioForcedChoiceTest
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from .consent_science_of_learning import consent_cococo_science_of_learning

SONG_MANIFEST = Path("static/songs.csv")
HEARING_CHECK_MANIFEST = Path("static/hearing_check.csv")
N_RATING_TRIALS_PER_PARTICIPANT = 20
N_RATINGS_PER_SONG = 5
MIN_MUSIC_RESPONSE_TIME = 10.0
MAX_EXPECTED_MUSIC_TRIAL_DURATION = 60.0
EXPECTED_TRIAL_DURATION = 40
SONG_MANIFEST_COLUMNS = {"track_id", "pair_id", "s3_url", "http_url", "is_parent"}

DURATION = N_RATING_TRIALS_PER_PARTICIPANT * EXPECTED_TRIAL_DURATION + 30
PAYMENT = 12*DURATION/3600

def load_songs():
    if not SONG_MANIFEST.exists():
        raise FileNotFoundError(
            f"Song manifest not found at {SONG_MANIFEST}. "
            "Create a CSV with columns 'track_id', 'pair_id', 's3_url', "
            "'http_url', and 'is_parent'."
        )

    with SONG_MANIFEST.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing_columns = SONG_MANIFEST_COLUMNS.difference(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                f"{SONG_MANIFEST} is missing required columns: "
                f"{', '.join(sorted(missing_columns))}."
            )
        songs = []
        for row_number, row in enumerate(reader, start=2):
            song = {column: row[column].strip() for column in SONG_MANIFEST_COLUMNS}
            song["manifest_row"] = row_number
            song["is_parent"] = parse_bool(song["is_parent"], song["track_id"])
            songs.append(song)

    if not songs:
        raise ValueError(f"{SONG_MANIFEST} must contain at least one song.")

    track_ids = [song["track_id"] for song in songs]
    if any(not track_id for track_id in track_ids):
        raise ValueError(f"All rows in {SONG_MANIFEST} must have a track_id.")

    missing_pair_ids = [song["track_id"] for song in songs if not song["pair_id"]]
    if missing_pair_ids:
        raise ValueError(
            f"The following songs do not have pair_id values: "
            f"{', '.join(missing_pair_ids)}."
        )

    invalid_s3_urls = [
        song["track_id"] for song in songs if not song["s3_url"].startswith("s3://")
    ]
    if invalid_s3_urls:
        raise ValueError(
            f"The following songs do not have s3:// s3_url values: "
            f"{', '.join(invalid_s3_urls)}."
        )

    invalid_http_urls = [
        song["track_id"]
        for song in songs
        if not song["http_url"].startswith(("http://", "https://"))
    ]
    if invalid_http_urls:
        raise ValueError(
            f"The following songs do not have HTTP(S) http_url values: "
            f"{', '.join(invalid_http_urls)}."
        )

    return songs


def parse_bool(value, track_id):
    normalized_value = value.strip().lower()
    if normalized_value in {"true", "1", "yes"}:
        return True
    if normalized_value in {"false", "0", "no"}:
        return False
    raise ValueError(
        f"is_parent for track_id '{track_id}' must be true or false, not {value!r}."
    )


def get_nodes():
    return [
        StaticNode(
            definition={
                "track_id": song["track_id"],
                "pair_id": song["pair_id"],
                "s3_url": song["s3_url"],
                "http_url": song["http_url"],
                "is_parent": song["is_parent"],
                "manifest_row": song["manifest_row"],
            },
            assets={
                "stimulus_audio": asset(
                    song["http_url"],
                    extension=".mp3",
                    description=(
                        f"Music rating stimulus {song['track_id']} "
                        f"(row {song['manifest_row']})"
                    ),
                )
            },
        )
        for song in load_songs()
    ]


if __name__ == "__main__":
    songs = load_songs()
    print(f"Found {len(songs)} songs in {SONG_MANIFEST}:")
    for song in songs:
        print(f"- {song['track_id']}: {song['http_url']}")


class MusicRatingTrial(StaticTrial):
    time_estimate = EXPECTED_TRIAL_DURATION

    def html5_audio_prompt(self):
        audio_url = self.assets["stimulus_audio"].url
        prompt = tags.div()
        with prompt:
            tags.p(
                Markup(
                    """
                    Please listen to the music clip until you are confident about your opinion, then rate it on a scale from very bad (1) to very good (8).
                    """
                )
            )
            with tags.audio(
                id="music-rating-audio",
                controls=True,
                autoplay=True,
                preload="auto",
                style="width: 100%; max-width: 720px; margin: 1rem 0;",
            ):
                tags.source(src=audio_url, type="audio/mpeg")
                tags.span(
                    "Your browser does not support HTML5 audio playback. "
                    "Please try a different browser."
                )
        return prompt

    def show_trial(self, experiment, participant):
        return ModularPage(
            "music_rating",
            self.html5_audio_prompt(),
            RatingControl(
                values=8,
                min_description="1 = Very bad",
                max_description="8 = Very good",
            ),
            events={
                "playStimulus": Event(
                    is_triggered_by="trialStart",
                    js="""
                    const audio = document.getElementById("music-rating-audio");
                    if (audio) {
                        audio.play().catch(() => {});
                    }
                    """,
                ),
                "submitEnable": Event(
                    is_triggered_by="trialStart",
                    delay=MIN_MUSIC_RESPONSE_TIME,
                ),
            },
            progress_display=ProgressDisplay(
                [ProgressStage(time=MAX_EXPECTED_MUSIC_TRIAL_DURATION)]
            ),
            time_estimate=self.time_estimate,
        )


class MusicRatingTrialMaker(StaticTrialMaker):
    @staticmethod
    def participant_rated_pair_ids(participant):
        return {
            trial.definition["pair_id"]
            for trial in participant.alive_trials
            if isinstance(trial, MusicRatingTrial) and trial.definition.get("pair_id")
        }

    def custom_network_filter(self, candidates, participant):
        rated_pair_ids = self.participant_rated_pair_ids(participant)
        return [
            network
            for network in candidates
            if network.head
            and network.head.definition.get("pair_id") not in rated_pair_ids
        ]


class Exp(psynet.experiment.Experiment):
    label = "Music Rating"
    test_n_bots = 1

    timeline = Timeline(
        consent_cococo_science_of_learning(DURATION=round(DURATION/60), PAYMENT=round(PAYMENT, 2)),
        InfoPage(
            Markup(
                f"""
                <p>Welcome! In this experiment you will listen to {N_RATING_TRIALS_PER_PARTICIPANT} music clips
                and rate each clip on a scale from very bad (1) to very good (8).</p>
                <p>Before the ratings begin, we will check that your audio playback
                is working.</p>
                """
            ),
            time_estimate=5,
        ),
        VolumeCalibration(),
        AudioForcedChoiceTest(
            csv_path=str(HEARING_CHECK_MANIFEST),
            answer_options=["dog", "bird"],
            performance_threshold=2,
            instructions="""
                <p>You will now complete a brief audio check.</p>
                <p>On each page, listen to the sound and select which animal you
                heard. You need to answer at least two out of three correctly to
                continue.</p>
            """,
            question="Which animal did you hear?",
        ),
        InfoPage(
            Markup(
                """
                <p>You passed the audio check.</p>
                <p>On each rating trial, please listen to the clip before answering.
                You may replay the clip if needed.</p>
                """
            ),
            time_estimate=5,
        ),
        MusicRatingTrialMaker(
            id_="music_ratings",
            trial_class=MusicRatingTrial,
            nodes=get_nodes,
            recruit_mode="n_trials",
            expected_trials_per_participant=N_RATING_TRIALS_PER_PARTICIPANT,
            max_trials_per_participant=N_RATING_TRIALS_PER_PARTICIPANT,
            target_trials_per_node=N_RATINGS_PER_SONG,
            allow_repeated_nodes=True,
        ),
        SuccessfulEndPage(),
    )

    def test_experiment(self):
        super().test_experiment()

        assert Participant.query.count() == self.test_n_bots
        assert MusicRatingTrial.query.count() == N_RATING_TRIALS_PER_PARTICIPANT
        assert Asset.query.count() >= len(load_songs())

    def test_check_bot(self, bot: Bot, **kwargs):
        super().test_check_bot(bot, **kwargs)
        rating_trials = [
            trial
            for trial in bot.alive_trials
            if isinstance(trial, MusicRatingTrial)
        ]
        assert len(rating_trials) == N_RATING_TRIALS_PER_PARTICIPANT
        pair_ids = [trial.definition["pair_id"] for trial in rating_trials]
        assert len(pair_ids) == len(set(pair_ids))
