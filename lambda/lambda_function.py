"""Alexa skill: "Alexa, open train times" / "Alexa, ask train times when's the next train at Franklin".

Runs on Amazon's free Alexa-hosted service. Every request lands in `handler`.
"""
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.utils import is_request_type, is_intent_name, get_slot_value

import config
import mta

STATIONS = mta.STATIONS[config.CORRIDOR]

DIRECTION_SLOT = {
    "manhattan": "N", "uptown": "N", "the city": "N", "northbound": "N",
    "brooklyn": "S", "downtown": "S", "southbound": "S",
    "both": None, "both ways": None, "either": None,
}
STATION_SLOT = {
    "franklin": "franklin", "franklin avenue": "franklin", "franklin ave": "franklin",
    "nostrand": "nostrand", "nostrand avenue": "nostrand", "nostrand ave": "nostrand",
}


def _report(station_keys, direction):
    """Build the spoken answer for one or more stations."""
    sentences = []
    for key in station_keys:
        station = STATIONS[key]
        try:
            arrivals = mta.next_arrivals(station, limit=config.TRAINS_TO_READ)
        except Exception as exc:  # feed down, timeout, etc.
            print(f"[train-times] feed error for {key}: {exc!r}")
            sentences.append(f"I couldn't reach the MTA feed for {station.name} just now.")
            continue
        sentences.append(mta.speak(station, arrivals, direction))
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
        station_key = STATION_SLOT.get(station_word)
        direction = DIRECTION_SLOT.get(direction_word, config.DEFAULT_DIRECTION) if direction_word else config.DEFAULT_DIRECTION
        if direction_word and direction_word not in DIRECTION_SLOT:
            direction = config.DEFAULT_DIRECTION
        stations = [station_key] if station_key else config.DEFAULT_STATIONS
        speech = _report(stations, direction)
        return handler_input.response_builder.speak(speech).set_should_end_session(True).response


class HelpHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speech = ("You can say: when's the next train at Franklin, "
                  "next Brooklyn-bound train at Nostrand, or just: train times. "
                  "Which would you like?")
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
        speech = "Sorry, I didn't get that. Try: when's the next train at Franklin?"
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
