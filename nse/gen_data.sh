for s in 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0; do
    python3 1_data_test_gen.py -fb 1.0 -s $s -dt 0.02
done

for s in 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0; do
    python3 1_data_test_gen.py -fb 0.0 -s $s -dt 0.01
done

for s in 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0; do
    python3 1_data_test_gen.py -fb 1.0 -s $s -dt 0.01
done

python3 1_data_gen.py -fr 2 -dt 0.02 -Nf 16
python3 1_data_gen.py -fr 2 -dt 0.01 -Nf 16