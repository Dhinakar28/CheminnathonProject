from src.anomaly import train_anomaly

if __name__ == '__main__':
    print('Starting anomaly train test...')
    res = train_anomaly('data/raw/ai4i2020.csv', outdir='models_test_anom', do_feature_engineering=False)
    print('Result:', res)
