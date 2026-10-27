"""Alexa skill: "Alexa, open franklin board" / "Alexa, ask franklin board when's the next train at Franklin".

Runs on Amazon's free Alexa-hosted service. Every request lands in `handler`.
"""
import traceback

# If anything below fails to load on Amazon's servers, the skill still answers,
# and it SAYS what went wrong instead of Amazon's generic "there was a problem".
_IMPORT_ERROR = None
try:
    from ask_sdk_core.skill_builder import SkillBuilder
    from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
    from ask_sdk_core.utils import is_request_type, is_intent_name, get_slot_value
    import config
    import mta
except Exception:  # noqa: BLE001
    _IMPORT_ERROR = traceback.format_exc()
    print("[train-times] IMPORT FAILED\n" + _IMPORT_ERROR)


def _plain_response(text):
    return {"version": "1.0",
            "response": {"outputSpeech": {"type": "PlainText", "text": text[:7000]},
                         "shouldEndSession": True}}


if _IMPORT_ERROR:
    def handler(event, context):
        last = _IMPORT_ERROR.strip().splitlines()[-1]
        return _plain_response("The train times code could not start. The error is: " + last)
else:

    STATIONS = mta.STATIONS[config.CORRIDOR]

    DIRECTION_SLOT = {
        "manhattan": "N", "uptown": "N", "the city": "N", "northbound": "N",
        "brooklyn": "S", "downtown": "S", "southbound": "S", "euclid": "S", "euclid avenue": "S",
        "both": None, "both ways": None, "either": None,
    }
    LINE_SLOT = {
        "a": "A", "a train": "A", "the a": "A", "eh": "A", "hey": "A",
        "c": "C", "c train": "C", "the c": "C", "see": "C", "sea": "C",
        "shuttle": "FS", "the shuttle": "FS", "franklin shuttle": "FS", "s": "FS", "s train": "FS",
        "2": "2", "two": "2", "3": "3", "three": "3", "4": "4", "four": "4", "5": "5", "five": "5",
    }
    STATION_SLOT = {
        "franklin": "franklin", "franklin avenue": "franklin", "franklin ave": "franklin",
        "nostrand": "nostrand", "nostrand avenue": "nostrand", "nostrand ave": "nostrand",
    }


    def _report(station_keys, direction, line=None, direction_was_asked=False):
        """Build the spoken answer for one or more stations."""
        sentences = []
        # Only say "toward Manhattan" when it isn't the everyday default.
        mention = direction_was_asked or direction != config.DEFAULT_DIRECTION
        mta.prefetch([STATIONS[k] for k in station_keys])  # all feeds at once
        for key in station_keys:
            station = STATIONS[key]
            try:
                arrivals = mta.next_arrivals(station, limit=12)
            except Exception as exc:  # feed down, timeout, etc.
                print(f"[train-times] feed error for {key}: {exc!r}")
                sentences.append(f"I couldn't reach the MTA feed for {station.name} just now.")
                continue
            sentences.append(mta.speak(station, arrivals, direction, line=line,
                                       mention_direction=mention, limit=config.TRAINS_TO_READ))
        return " ".join(sentences)


    class LaunchHandler(AbstractRequestHandler):
        def can_handle(self, handler_input):
            return is_request_type("LaunchRequest")(handler_input)

        def handle(self, handler_input):
            speech = _report(config.DEFAULT_STATIONS, config.DEFAULT_DIRECTION)
            return handler_input.response_builder.speak(speech).set_should_end_session(True).response


    class NextTrainHandler(AbstractRequestHandler):
        def can_handle(self, handler_input):
            return is_intent_name("NextTrainIntent")(handler_input)

        def handle(self, handler_input):
            station_word = (get_slot_value(handler_input, "station") or "").lower().strip()
            direction_word = (get_slot_value(handler_input, "direction") or "").lower().strip()
            line_word = (get_slot_value(handler_input, "line") or "").lower().strip()
            station_key = STATION_SLOT.get(station_word)
            direction_known = direction_word in DIRECTION_SLOT
            direction = DIRECTION_SLOT[direction_word] if direction_known else config.DEFAULT_DIRECTION
            line = LINE_SLOT.get(line_word) or LINE_SLOT.get(line_word.replace(" train", "").replace("the ", ""))
            if line_word and not line:
                print(f"[train-times] unknown line word: {line_word!r}")
            stations = [station_key] if station_key else config.DEFAULT_STATIONS
            if line and not station_key:
                # "when's the C train" with no station: answer for the stations that have it.
                stations = [k for k in config.DEFAULT_STATIONS if line in STATIONS[k].lines] or stations
            speech = _report(stations, direction, line=line, direction_was_asked=direction_known)
            return handler_input.response_builder.speak(speech).set_should_end_session(True).response


    class HelpHandler(AbstractRequestHandler):
        def can_handle(self, handler_input):
            return is_intent_name("AMAZON.HelpIntent")(handler_input)

        def handle(self, handler_input):
            speech = ("You can say: when's the C train at Franklin, "
                      "next train at Nostrand, trains toward Euclid at Nostrand, "
                      "or just: franklin board. Which would you like?")
            return handler_input.response_builder.speak(speech).ask(speech).response


    class StopHandler(AbstractRequestHandler):
        def can_handle(self, handler_input):
            return (is_intent_name("AMAZON.StopIntent")(handler_input)
                    or is_intent_name("AMAZON.CancelIntent")(handler_input)
                    or is_intent_name("AMAZON.NavigateHomeIntent")(handler_input)
                    or is_request_type("SessionEndedRequest")(handler_input))

        def handle(self, handler_input):
            return handler_input.response_builder.speak("Okay.").set_should_end_session(True).response


    class FallbackHandler(AbstractRequestHandler):
        def can_handle(self, handler_input):
            return is_intent_name("AMAZON.FallbackIntent")(handler_input)

        def handle(self, handler_input):
            speech = "Sorry, I didn't get that. Try: when's the C train at Franklin?"
            return handler_input.response_builder.speak(speech).ask(speech).response


    class CatchAll(AbstractExceptionHandler):
        def can_handle(self, handler_input, exception):
            return True

        def handle(self, handler_input, exception):
            print(f"[train-times] unhandled: {exception!r}")
            speech = "Sorry, something went wrong reading the train times. Please try again."
            return handler_input.response_builder.speak(speech).set_should_end_session(True).response


    sb = SkillBuilder()
    for h in (LaunchHandler(), NextTrainHandler(), HelpHandler(), StopHandler(), FallbackHandler()):
        sb.add_request_handler(h)
    sb.add_exception_handler(CatchAll())
    handler = sb.lambda_handler()


# Alexa-hosted Python looks for this exact name (lambda_function.lambda_handler).
lambda_handler = handler
