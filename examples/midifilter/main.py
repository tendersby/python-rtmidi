#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# midifilter.py
#
"""Simple MIDI filter/ processor."""

import argparse
import logging
import Queue
import sys
import threading
import time

import rtmidi
from rtmidi.midiutil import open_midiport

from .filters import *


log = logging.getLogger("midifilter")


class MidiDispatcher(threading.Thread):
    def __init__(self, midiin, midiout, *filters):
        super(MidiDispatcher, self).__init__()
        self.midiin = midiin
        self.midiout = midiout
        self.filters = filters
        self._wallclock = time.time()
        self.queue = Queue.Queue()

    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime
        log.debug("IN: @%0.6f %r", self._wallclock, message)
        self.queue.put((message, self._wallclock))

    def run(self):
        log.debug("Attaching MIDI input callback handler.")
        self.midiin.set_callback(self)

        while True:
            event = self.queue.get()

            if event is None:
                break

            events = [event]

            for filter_ in self.filters:
                events = list(filter_.process(events))

            for event in events:
                log.debug("Out: @%0.6f %r", event[1], event[0])
                self.midiout.send_message(event[0])

    def stop(self):
        self.queue.put(None)


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-m',  '--mpresstocc', action="store_true",
        help='Map mono pressure (channel aftertouch) to CC')
    parser.add_argument('-r',  '--mapccrange', action="store_true",
        help='Map controller value range to min/max value range')
    parser.add_argument('-t',  '--transpose', action="store_true",
        help='Transpose note on/off event note values')
    parser.add_argument('-i',  '--inport', type=int,
        help='MIDI input port number (default: ask)')
    parser.add_argument('-o',  '--outport', type=int,
        help='MIDI output port number (default: ask)')
    parser.add_argument('-v',  '--verbose', action="store_true",
        help='verbose output')
    parser.add_argument('filter-args', nargs="*", type=int,
        help='MIDI filter argument(s)')

    args = parser.parse_args(args if args is not None else sys.argv)

    logging.basicConfig(format="%(name)s: %(levelname)s - %(message)s",
        level=logging.DEBUG if args.verbose else logging.WARNING,)

    try:
        value = int(args.pop(0))
    except (IndexError, TypeError):
        value = 12

    try:
        midiin, inport_name = select_midiport(args.inport, "input")
        midiout, outport_name = select_midiport(args.outport, "input")
    except IOError as exc:
        print(exc)
        return 1

    filters = []
    if args.transpose:
        filters.append(Transpose(transpose=args.filter_args[0]))
    if mpresstocc:
        MonoPressureToCC(cc=args.filter_args[0]))
    if mapcc:
        filters.append(MapControllerValue(*args.filter_args))

    dispatcher = MidiDispatcher(midiin, midiout, *filters)

    print("Entering main loop. Press Control-C to exit.")
    try:
        dispatcher.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        dispatcher.stop()
        dispatcher.join()
        print('')
    finally:
        print("Exit.")

        midiin.close_port()
        midiout.close_port()

        del midiin
        del midiout

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
