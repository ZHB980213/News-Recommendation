import os
import sys
os.chdir('/home/peitian_zhang/Codes/News-Recommendation')
sys.path.append('/home/peitian_zhang/Codes/News-Recommendation')

import torch
from utils.utils import evaluate,train,prepare,load_hparams,test

if __name__ == "__main__":

    hparams = {
        'name':'baseline-mha-cnn',
        'dropout_p':0.2,
        'query_dim':200,
        'embedding_dim':300,
        'value_dim':16,
        'head_num':16,
        'attrs': ['title'],
    }
    hparams = load_hparams(hparams)
    device = torch.device(hparams['device'])
    vocab, loaders = prepare(hparams)

    if hparams['select'] == 'greedy':
        from models.baseline_MHA_MHA import GCAModel_greedy
        gcaModel = GCAModel_greedy(vocab=vocab,hparams=hparams).to(device)
    
    elif hparams['select'] == 'pipeline':
        from models.baseline_MHA_MHA import GCAModel_pipeline
        gcaModel = GCAModel_pipeline(vocab=vocab,hparams=hparams).to(device)

    if hparams['mode'] == 'dev':
        gcaModel.load_state_dict(torch.load(hparams['save_path']))
        print("testing...")
        evaluate(gcaModel,hparams,loaders[1])

    elif hparams['mode'] == 'train':
        train(gcaModel, hparams, loaders, tb=True)
    
    elif hparams['mode'] == 'test':
        test(gcaModel, hparams, loaders[0])