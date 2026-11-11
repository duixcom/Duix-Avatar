set -eu
cc -O2 -ffp-contract=off -I include -I . src/denoise.c src/rnn.c src/rnn_data.c src/rnn_reader.c src/pitch.c src/kiss_fft.c src/celt_lpc.c rnnoise_demo.c -lm -o rnnoise_new
