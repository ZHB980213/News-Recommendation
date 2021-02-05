import numpy as np
from torch.utils.data import Dataset,IterableDataset
from .utils import newsample,getId2idx,word_tokenize_vocab,getVocab

class MIND_map(Dataset):
    """ Map style dataset

    Args:
        hparams(dict): pre-defined dictionary of hyper parameters
        mode(str): train/test
        news_file(str): path of news_file
        behaviors_file(str): path of behaviors_file
    """
    def __init__(self,hparams,news_file,behaviors_file,col_spliter='\t'):
        # initiate the whole iterator
        self.npratio = hparams['npratio']
        self.news_file = news_file
        self.behaviors_file = behaviors_file
        self.col_spliter = col_spliter        
        self.batch_size = hparams['batch_size']
        self.title_size = hparams['title_size']
        self.his_size = hparams['his_size']
        self.attrs = hparams['attrs']
        self.k = hparams['k']

        self.vocab = getVocab('data/dictionaries/vocab_{}_{}.pkl'.format(hparams['scale'],'_'.join(hparams['attrs'])))
        self.nid2index = getId2idx('data/dictionaries/nid2idx_{}_train.json'.format(hparams['scale']))
        self.uid2index = getId2idx('data/dictionaries/uid2idx_{}.json'.format(hparams['scale']))
    
    def __len__(self):
        if not hasattr(self, "news_title_array"):
            self.init_news()

        if not hasattr(self, "impr_indexes"):
            self.init_behaviors()

        return len(self.labels)
    
    def init_news(self):
        """ 
            init news information given news file, such as news_title_array.
        """

        title_token = [[0]*self.title_size]
        # category_token = [[0]]
        # subcategory_token = [[0]]

        title_pad = [[self.title_size]]
        
        with open(self.news_file,"r",encoding='utf-8') as rd:

            for idx in rd:
                nid, vert, subvert, title, ab, url, _, _ = idx.strip("\n").split(
                    self.col_spliter
                )

                title = word_tokenize_vocab(title,self.vocab)
                title_token.append(title[:self.title_size] + [0] * (self.title_size - len(title)))
                title_pad.append([max(self.title_size - len(title), 0)])
                # category_token.append([self.vocab[vert]])
                # subcategory_token.append([self.vocab[subvert]])
        
        self.news_title_array = np.asarray(title_token)
        # self.news_category_array = np.asarray(category_token)
        # self.news_subcategory_array = np.asarray(subcategory_token)

        self.title_pad = np.asarray(title_pad)

    def init_behaviors(self):
        """ 
            init behavior logs given behaviors file.
        """

        # list of click history of each log
        self.histories = []
        # list of impression of each log
        self.imprs = []
        # list of labels of each news of each log
        self.labels = []
        # list of impressions
        self.impr_indexes = []
        # user ids
        self.uindexes = []
        # history padding
        self.his_pad = []

        with open(self.behaviors_file, "r",encoding='utf-8') as rd:
            impr_index = 1
            for idx in rd:
                uid, time, history, impr = idx.strip("\n").split(self.col_spliter)[-4:]
                
                history = [self.nid2index[i] for i in history.split()]
                
                if self.k:
                    # guarantee there are at least k history not masked
                    self.his_pad.append(min(max(self.his_size - len(history),0), self.his_size - self.k))
                else:
                    self.his_pad.append(max(self.his_size - len(history),0))
                # tailor user's history or pad 0
                history = history[:self.his_size] + [0] * (self.his_size - len(history))
                impr_news = [self.nid2index[i.split("-")[0]] for i in impr.split()]
                
                label = [int(i.split("-")[1]) for i in impr.split()]
                
                uindex = self.uid2index[uid] if uid in self.uid2index else 0

                self.histories.append(history)
                self.imprs.append(impr_news)
                self.labels.append(label)
                self.impr_indexes.append(impr_index)
                self.uindexes.append(uindex)

                impr_index += 1

    def __getitem__(self, idx):
        """ parse behavior log No.idx to training example

        Args:
            idx (int): impression index, start from zero

        Returns:
            dict of training data, including |npratio+1| candidate news word vector, |his_size+1| clicked news word vector etc.
        """
        if not hasattr(self, "news_title_array"):
            self.init_news()

        if not hasattr(self, "impr_indexes"):
            self.init_behaviors()
            

        impr_label = self.labels[idx]
        impr = self.imprs[idx]

        # user clicked news
        poss = []
        # user not clicked news
        negs = []

        for news, click in zip(impr, impr_label):
            if click == 1:
                poss.append(news)
            else:
                negs.append(news)

        for p in poss:
            # can't find a more elegant way
            
            
            candidate_title_index = []
            # candidate_category_index = []
            # candidate_subcategory_index = []
            user_index = []
            his_mask = np.zeros((self.his_size,1),dtype=bool)
            
            label = [1] + [0] * self.npratio

            neg_list, neg_pad = newsample(negs, self.npratio)

            candidate_title_index = self.news_title_array[[p] + neg_list]
            # candidate_category_index = self.news_category_array[[p] + neg_list]
            # candidate_subcategory_index = self.news_subcategory_array[[p] + neg_list]
            
            click_title_index = self.news_title_array[self.histories[idx]]
            # click_category_index = self.news_category_array[self.histories[idx]]
            # click_subcategory_index = self.news_subcategory_array[self.histories[idx]]
            # pad in title
            candidate_title_pad = [(self.title_size - i[0])*[1] + i[0]*[0] for i in self.title_pad[[p] + neg_list]]
            click_title_pad = [(self.title_size - i[0])*[1] + i[0]*[0] for i in self.title_pad[self.histories[idx]]]
            
            # pad in candidate
            # candidate_mask = [1] * neg_pad + [0] * (self.npratio + 1 - neg_pad)

            # in case the user has no history records, do not mask
            if self.his_pad[idx] == self.his_size or self.his_pad[idx] == 0:
                his_mask = his_mask
            else:
                # print(self.his_pad[idx])
                his_mask[-self.his_pad[idx]:] = [True]

            # impression_index not needed in training
            # impr_index = self.impr_indexes[idx]
            
            user_index.append(self.uindexes[idx])

            return {
                "user_index": np.asarray(user_index),
                # "cdd_mask": np.asarray(neg_pad),
                "his_mask": his_mask,
                "clicked_title": click_title_index,
                # "clicked_category":click_category_index,
                # "clicked_subcategory":click_subcategory_index,
                "clicked_title_pad": np.asarray(click_title_pad),
                "candidate_title": candidate_title_index,
                # "candidate_category": candidate_category_index,
                # "candidate_subcategory": candidate_subcategory_index,
                "candidate_title_pad": np.asarray(candidate_title_pad),
                "labels": np.asarray(label)
            }

class MIND_iter(IterableDataset):
    """ Iterator style dataset

    Args:
        hparams(dict): pre-defined dictionary of hyper parameters
        mode(str): train/test
        news_file(str): path of news_file
        behaviors_file(str): path of behaviors_file
    """
    def __init__(self,hparams,news_file,behaviors_file,mode='test',col_spliter='\t'):
        # initiate the whole iterator
        self.news_file = news_file
        self.behaviors_file = behaviors_file
        self.col_spliter = col_spliter        
        self.batch_size = hparams['batch_size']
        self.title_size = hparams['title_size']
        self.his_size = hparams['his_size']
        self.k = hparams['k']

        self.vocab = getVocab('data/dictionaries/vocab_{}_{}.pkl'.format(hparams['scale'],'_'.join(hparams['attrs'])))
        self.nid2index = getId2idx('data/dictionaries/nid2idx_{}_{}.json'.format(hparams['scale'],mode))
        self.uid2index = getId2idx('data/dictionaries/uid2idx_{}.json'.format(hparams['scale']))
    
    def init_news(self):
        """ 
            init news information given news file, such as news_title_array.
        """

        title_token = [[0]*self.title_size]
        # category_token = [[0]]
        # subcategory_token = [[0]]

        title_pad = [[self.title_size]]
        
        with open(self.news_file,"r",encoding='utf-8') as rd:

            for idx in rd:
                nid, vert, subvert, title, ab, url, _, _ = idx.strip("\n").split(
                    self.col_spliter
                )

                title = word_tokenize_vocab(title,self.vocab)
                title_token.append(title[:self.title_size] + [0] * (self.title_size - len(title)))
                title_pad.append([max(self.title_size - len(title), 0)])

                # category_token.append([self.vocab[vert]])
                # subcategory_token.append([self.vocab[subvert]])
        
        self.news_title_array = np.asarray(title_token)
        # self.news_category_array = np.asarray(category_token)
        # self.news_subcategory_array = np.asarray(subcategory_token)

        self.title_pad = np.asarray(title_pad)

    def init_behaviors(self):
        """ 
            init behavior logs given behaviors file.
        """

        # list of click history of each log
        self.histories = []
        # list of impression of each log
        self.imprs = []
        # list of labels of each news of each log
        self.labels = []
        # list of impressions
        self.impr_indexes = []
        # user ids
        self.uindexes = []
        # history padding
        self.his_pad = []

        with open(self.behaviors_file, "r",encoding='utf-8') as rd:
            impr_index = 1
            for idx in rd:
                uid, time, history, impr = idx.strip("\n").split(self.col_spliter)[-4:]
                
                history = [self.nid2index[i] for i in history.split()]
                
                if self.k:
                    # guarantee there are at least k history not masked
                    self.his_pad.append(min(max(self.his_size - len(history),0), self.his_size - self.k))
                else:
                    self.his_pad.append(max(self.his_size - len(history),0))
                    
                # tailor user's history or pad 0
                history = history[:self.his_size] + [0] * (self.his_size - len(history))
        
                impr_news = [self.nid2index[i.split("-")[0]] for i in impr.split()]
                try:
                    label = [int(i.split("-")[1]) for i in impr.split()]
                except:
                    print(impr,impr_index)
                uindex = self.uid2index[uid] if uid in self.uid2index else 0

                self.histories.append(history)
                self.imprs.append(impr_news)
                self.labels.append(label)
                self.impr_indexes.append(impr_index)
                self.uindexes.append(uindex)
                impr_index += 1

    def __iter__(self):
        """ parse behavior logs into training examples

        Yields:
            dict of training data, including 1 candidate news word vector, |his_size+1| clicked news word vector etc.
        """
        if not hasattr(self, "news_title_array"):
            self.init_news()

        if not hasattr(self, "impr_indexes"):
            self.init_behaviors()
        
        for index,impr_label in enumerate(self.labels):
            impr = self.imprs[index]
        
            for news, label in zip(impr, impr_label):
                # indicate the candidate news title vector from impression
                candidate_title_index = []
                # candidate_category_index = []
                # candidate_subcategory_index = []

                # indicate the impression where the news in
                impr_index = []
                # indicate user ID
                user_index = []
                # indicate history mask
                his_mask = np.zeros((self.his_size,1),dtype=bool)

                # indicate whether the news is clicked
                label = label
                # append the news title vector corresponding to news variable, in order to generate [news_title_vector]
                candidate_title_index.append(self.news_title_array[news])
                # candidate_category_index.append(self.news_category_array[news])
                # candidate_subcategory_index.append(self.news_subcategory_array[news])
                
                # append the news title vector corresponding to news variable
                click_title_index = self.news_title_array[self.histories[index]]
                # click_category_index = self.news_category_array[self.histories[index]]
                # click_subcategory_index = self.news_subcategory_array[self.histories[index]]

                impr_index = self.impr_indexes[index]
                user_index.append(self.uindexes[index])

                candidate_title_pad = [(self.title_size - self.title_pad[news][0])*[1] + self.title_pad[news][0]*[0]]
                click_title_pad = [(self.title_size - i[0])*[1] + i[0]*[0] for i in self.title_pad[self.histories[index]]]

            
                # in case the user has no history records, do not mask
                if self.his_pad[index] == self.his_size or self.his_pad[index] == 0:
                    his_mask = his_mask
                else:
                    # print(self.his_pad[idx])
                    his_mask[-self.his_pad[index]:] = [True]
                
                yield {
                    "impression_index": impr_index,
                    "user_index": np.asarray(user_index),
                    "clicked_title": click_title_index,
                    # "clicked_category":click_category_index,
                    # "clicked_subcategory":click_subcategory_index,
                    "clicked_title_pad": np.asarray(click_title_pad),
                    "his_mask":his_mask,
                    "candidate_title": np.asarray(candidate_title_index),
                    # "candidate_category": np.asarray(candidate_category_index),
                    # "candidate_subcategory": np.asarray(candidate_subcategory_index),
                    "candidate_title_pad": np.asarray(candidate_title_pad),
                    "labels": np.asarray(label)
                }

class MIND_test(IterableDataset):
    """ Iterator style dataset

    Args:
        hparams(dict): pre-defined dictionary of hyper parameters
        mode(str): train/test
        news_file(str): path of news_file
        behaviors_file(str): path of behaviors_file
    """
    def __init__(self,hparams,news_file,behaviors_file,mode='test',col_spliter='\t'):
        # initiate the whole iterator
        self.news_file = news_file
        self.behaviors_file = behaviors_file
        self.col_spliter = col_spliter        
        self.batch_size = hparams['batch_size']
        self.title_size = hparams['title_size']
        self.his_size = hparams['his_size']
        self.k = hparams['k']

        self.vocab = getVocab('data/dictionaries/vocab_large_{}.pkl'.format('_'.join(hparams['attrs'])))
        self.nid2index = getId2idx('data/dictionaries/nid2idx_large_dev.json')
        self.uid2index = getId2idx('data/dictionaries/uid2idx_large_dev.json')
    
    def init_news(self):
        """ 
            init news information given news file, such as news_title_array.
        """

        title_token = [[0]*self.title_size]
        # category_token = [[0]]
        # subcategory_token = [[0]]

        title_pad = [[self.title_size]]
        
        with open(self.news_file,"r",encoding='utf-8') as rd:

            for idx in rd:
                nid, vert, subvert, title, ab, url, _, _ = idx.strip("\n").split(
                    self.col_spliter
                )

                title = word_tokenize_vocab(title,self.vocab)
                title_token.append(title[:self.title_size] + [0] * (self.title_size - len(title)))
                title_pad.append([max(self.title_size - len(title), 0)])

                # category_token.append([self.vocab[vert]])
                # subcategory_token.append([self.vocab[subvert]])
        
        self.news_title_array = np.asarray(title_token)
        # self.news_category_array = np.asarray(category_token)
        # self.news_subcategory_array = np.asarray(subcategory_token)

        self.title_pad = np.asarray(title_pad)

    def init_behaviors(self):
        """ 
            init behavior logs given behaviors file.
        """

        # list of click history of each log
        self.histories = []
        # list of impression of each log
        self.imprs = []
        # list of impressions
        self.impr_indexes = []
        # user ids
        self.uindexes = []
        # history padding
        self.his_pad = []

        with open(self.behaviors_file, "r",encoding='utf-8') as rd:
            impr_index = 1
            for idx in rd:
                uid, time, history, impr = idx.strip("\n").split(self.col_spliter)[-4:]
                
                history = [self.nid2index[i] for i in history.split()]
                
                if self.k:
                    # guarantee there are at least k history not masked
                    self.his_pad.append(min(max(self.his_size - len(history),0), self.his_size - self.k))
                else:
                    self.his_pad.append(max(self.his_size - len(history),0))
                    
                # tailor user's history or pad 0
                history = history[:self.his_size] + [0] * (self.his_size - len(history))
        
                impr_news = [self.nid2index[i] for i in impr.split()]
                uindex = self.uid2index[uid] if uid in self.uid2index else 0

                self.histories.append(history)
                self.imprs.append(impr_news)
                self.impr_indexes.append(impr_index)
                self.uindexes.append(uindex)
                impr_index += 1

    def __iter__(self):
        """ parse behavior logs into training examples

        Yields:
            dict of training data, including 1 candidate news word vector, |his_size+1| clicked news word vector etc.
        """
        if not hasattr(self, "news_title_array"):
            self.init_news()

        if not hasattr(self, "impr_indexes"):
            self.init_behaviors()
        
        for index,impr in enumerate(self.imprs):
        
            for news in impr:
                # indicate the candidate news title vector from impression
                candidate_title_index = []
                # candidate_category_index = []
                # candidate_subcategory_index = []

                # indicate the impression where the news in
                impr_index = []
                # indicate user ID
                user_index = []
                # indicate history mask
                his_mask = np.zeros((self.his_size,1),dtype=bool)

                # append the news title vector corresponding to news variable, in order to generate [news_title_vector]
                candidate_title_index.append(self.news_title_array[news])
                # candidate_category_index.append(self.news_category_array[news])
                # candidate_subcategory_index.append(self.news_subcategory_array[news])
                
                # append the news title vector corresponding to news variable
                click_title_index = self.news_title_array[self.histories[index]]
                # click_category_index = self.news_category_array[self.histories[index]]
                # click_subcategory_index = self.news_subcategory_array[self.histories[index]]

                impr_index = self.impr_indexes[index]
                user_index.append(self.uindexes[index])

                candidate_title_pad = [(self.title_size - self.title_pad[news][0])*[1] + self.title_pad[news][0]*[0]]
                click_title_pad = [(self.title_size - i[0])*[1] + i[0]*[0] for i in self.title_pad[self.histories[index]]]

            
                # in case the user has no history records, do not mask
                if self.his_pad[index] == self.his_size or self.his_pad[index] == 0:
                    his_mask = his_mask
                else:
                    # print(self.his_pad[idx])
                    his_mask[-self.his_pad[index]:] = [True]
                
                yield {
                    "impression_index": impr_index,
                    "user_index": np.asarray(user_index),
                    "clicked_title": click_title_index,
                    # "clicked_category":click_category_index,
                    # "clicked_subcategory":click_subcategory_index,
                    "clicked_title_pad": np.asarray(click_title_pad),
                    "his_mask":his_mask,
                    "candidate_title": np.asarray(candidate_title_index),
                    # "candidate_category": np.asarray(candidate_category_index),
                    # "candidate_subcategory": np.asarray(candidate_subcategory_index),
                    "candidate_title_pad": np.asarray(candidate_title_pad),
                }