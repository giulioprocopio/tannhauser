(
~scPort = 57120;
~pyPort = 57121;

~includeFiles = (getenv("TNHSR_INCLUDES") ?? "").split(";")
.reject({ |s| s.isEmpty });

// MacOS with AirPods 2 seems to have issues with the default buffer size
// causing distortion. Setting it to 256 seems to fix the issue.
s.options.numInputBusChannels = 0;
s.options.hardwareBufferSize = 256;

thisProcess.openUDPPort(~scPort);
"sclang listening on UDP port 57120".postln;

s.waitForBoot({

    "SuperCollider audio server booted".postln;

    ~pyPort = NetAddr("127.0.0.1", ~pyPort);

    OSCdef(\quit, {
        "Quit received".postln;
        s.freeAll;
        s.quit;
        0.exit;
    }, '/quit');

    OSCdef(\statusReply, { |msg|
        var status = [
            1.0,
            s.numGroups.asFloat,
            s.numSynths.asFloat,
            s.numUGens.asFloat,
            s.avgCPU,
            s.peakCPU,
            s.avgCPU,
            s.sampleRate,
            s.actualSampleRate
        ];
        // For some reason, keeping integers in the tuple causes the Python OSC
        // library to fail parsing it, so we convert everything to float.
        ~pyPort.sendMsg("/status.reply", *status);
    }, '/status');

    SynthDef(\sample, { |freq = 440, amp = 0.2, dur = 1.0|
        var env = EnvGen.kr(Env.perc(0.01, dur, amp), doneAction: 2);
        var sig = SinOsc.ar(freq) * env;
        Out.ar(0, sig ! 2);
    }).add;

    OSCdef(\test, { |msg|
        var freq = msg[1] ? 440;
        var amp = msg[2] ? 0.2;
        var dur = msg[3] ? 1.0;
        var logMsg;

        logMsg = "Test received (freq: %, amp: %, dur: %)"
            .format(freq, amp, dur);
        logMsg.postln;

        Synth(\sample, [
            \freq, freq.asFloat, \amp, amp.asFloat, \dur, dur.asFloat
        ]);
    }, '/test');

    OSCdef(\scope, { |msg|
        var numChannels = msg[1] ? 2;
        AppClock.sched(0, {
            s.scope(numChannels);
            nil
        });
    }, '/scope');

    OSCdef(\freqscope, { |msg|
        var numChannels = msg[1] ? 2;
        AppClock.sched(0, {
            s.freqscope(numChannels);
            nil
        });
    }, '/freqscope');

    OSCdef(\ndefSet, { |msg|
        var ndefName, ndef, params;

        try {
            ndefName = msg[1].asSymbol;
            ndef = Ndef(ndefName);
            params = msg[2..];

            if (ndef.isNil.not, {
                params.pairsDo { |key, value|
                    ndef.set(key.asSymbol, value);
                };
                ("Ndef % set: %".format(ndefName, params)).postln;
            }, {
                ("Ndef % not found".format(ndefName)).postln;
            });
        } { |error|
            ("Error setting Ndef parameter: " ++ error.errorString).postln;
            error.dumpBackTrace;
        };
    }, '/ndef/set');

    ~notes = Dictionary.new;

    OSCdef(\noteOn, { |msg|
        var noteID = msg[1];
        var midi = msg[2];
        var velocity = msg[3] ? 0.8;
        ("Note on: % (%.2 Hz, velocity: %)"
            .format(noteID, midi.midicps, velocity)).postln;
    }, '/note/on');

    OSCdef(\noteOff, { |msg|
        var noteID = msg[1];
        ("Note off: %".format(noteID)).postln;
    }, '/note/off');

    OSCdef(\tdefPlay, { |msg|
        var tdefName = msg[1].asSymbol;
        var tdef = Tdef(tdefName);
        if (tdef.isNil.not, {
            tdef.play;
            ("Tdef % playing".format(tdefName)).postln;
        }, {
            ("Tdef % not found".format(tdefName)).postln;
        });
    }, '/tdef/play');

    OSCdef(\tdefStop, { |msg|
        var tdefName = msg[1].asSymbol;
        var tdef = Tdef(tdefName);
        if (tdef.isNil.not, {
            tdef.stop;
            ("Tdef % stopped".format(tdefName)).postln;
        }, {
            ("Tdef % not found".format(tdefName)).postln;
        });
    }, '/tdef/stop');

    OSCdef(\tdefPause, { |msg|
        var tdefName = msg[1].asSymbol;
        var tdef = Tdef(tdefName);
        if (tdef.isNil.not, {
            tdef.pause;
            ("Tdef % paused".format(tdefName)).postln;
        }, {
            ("Tdef % not found".format(tdefName)).postln;
        });
    }, '/tdef/pause');

    ~includeFiles.do { |filePath|
        ("Loading " ++ filePath).postln;
        filePath.load;
    };

    "SuperCollider ready".postln;

}, {

    "SuperCollider boot failed".postln;
    1.exit;

});
)
