# Mark 1: Embeddings followed by CNN-maxpool
# with conv done sequence-wise and maxpool done embedding dimension-wise
# just as in http://www.wildml.com/2015/12/implementing-a-cnn-for-text-classification-in-tensorflow/

import tensorflow as tf

from models.abstract_model import AbstractModel
from data_readers.text_data_reader import TextDataReader
from layers.embedding_layer import EmbeddingLayer
from layers.fully_connected_layer import FullyConnectedLayer
from layers.dropout_layer import DropoutLayer
from layers.conv_maxpool_layer import ConvMaxpoolLayer

from utilities import make_params_dict

PPL_DATA_DIR = '../data/peopleData/'


class Mark1(AbstractModel):

    def __init__(self, input_,
                 initialLearningRate, l2RegLambda,
                 vocabSize, embeddingDim,
                 filterSizes, numFeaturesPerFilter,
                 pooledKeepProb,
                 loggerFactory_=None):
        """        
        :type initialLearningRate: float 
        :type l2RegLambda: float
        :type pooledKeepProb: float 
        :type vocabSize: int
        :type embeddingDim: int
        """


        self.l2RegLambda = l2RegLambda
        self.pooledKeepProb = pooledKeepProb
        self.vocabSize = vocabSize
        self.embeddingDim = embeddingDim
        self.filterSizes = filterSizes
        self.numFeaturesPerFilter = numFeaturesPerFilter

        super().__init__(input_, initialLearningRate, loggerFactory_)
        self.print('l2 reg lambda: %0.7f' % l2RegLambda)

    def make_graph(self):

        inputNumCols = self.x.get_shape()[1].value

        # layer1: embedding
        layer1 = self.add_layers(EmbeddingLayer.new(self.vocabSize, self.embeddingDim),
                                 self.input['x'], (-1, inputNumCols))

        # layer2: a bunch of conv-maxpools
        layer2_outputs = []

        for filterSize in self.filterSizes:

            l = ConvMaxpoolLayer(layer1.output, layer1.output_shape,
                                 convParams_={'filterShape': (filterSize, self.embeddingDim),
                                              'numFeaturesPerFilter': self.numFeaturesPerFilter, 'activation': 'relu'},
                                 maxPoolParams_={'ksize': (inputNumCols - filterSize + 1, 1), 'padding': 'VALID'},
                                 loggerFactory=self.loggerFactory)

            layer2_outputs.append(l.output)


        layer2_outputShape = -1, self.numFeaturesPerFilter * len(self.filterSizes)
        layer2_output = tf.reshape(tf.concat(layer2_outputs, 3), layer2_outputShape)

        self.add_output(layer2_output, layer2_outputShape)

        # layer3: dropout
        self.add_layers(DropoutLayer.new(self.pooledKeepProb))

        # layer4: fully connected
        lastLayer = self.add_layers(FullyConnectedLayer.new(self.numClasses))

        self.l2Loss = self.l2RegLambda * (tf.nn.l2_loss(lastLayer.weights) + tf.nn.l2_loss(lastLayer.biases))


    @classmethod
    def quick_run(cls, runScale ='tiny', dataScale='tiny_fake_2', useCPU = True):

        # ok this is silly. But at least it's fast.
        vocabSize = TextDataReader.maker_from_premade_source(dataScale)(
            bucketingOrRandom = 'bucketing', batchSize_ = 50, minimumWords = 0).vocabSize

        params = [('initialLearningRate', [1e-3]),
                  ('l2RegLambda', [0]),
                  ('vocabSize', [vocabSize]),
                  ('embeddingDim', [32]),
                  ('filterSizes', [[2, 4], [1,3,5]]),
                  ('numFeaturesPerFilter', [8]),
                  ('pooledKeepProb', [1])]

        cls.run_thru_data(TextDataReader, dataScale, make_params_dict(params), runScale, useCPU)


    @classmethod
    def quick_learn(cls, runScale='small', dataScale='full_2occupations', useCPU=True):
        # ok this is silly. But at least it's fast.
        vocabSize = TextDataReader.maker_from_premade_source(dataScale)(
            bucketingOrRandom='bucketing', batchSize_=50, minimumWords=0).vocabSize

        params = [('initialLearningRate', [1e-3]),
                  ('l2RegLambda', [0]),
                  ('vocabSize', [vocabSize]),
                  ('embeddingDim', [300]),
                  ('filterSizes', [[1, 3, 5]]),
                  ('numFeaturesPerFilter', [8]),
                  ('pooledKeepProb', [1])]

        cls.run_thru_data(TextDataReader, dataScale, make_params_dict(params), runScale, useCPU)

    @classmethod
    def comparison_run(cls, runScale='small', dataScale='full_2occupations', useCPU=True):
        # ok this is silly. But at least it's fast.
        vocabSize = TextDataReader.maker_from_premade_source(dataScale)(
            bucketingOrRandom='bucketing', batchSize_=50, minimumWords=0).vocabSize

        params = [('initialLearningRate', [1e-3]),
                  ('l2RegLambda', [0, 1e-5]),
                  ('vocabSize', [vocabSize]),
                  ('embeddingDim', [64, 128, 300]),
                  ('filterSizes', [[1, 2, 4]]),
                  ('numFeaturesPerFilter', [16, 32, 64]),
                  ('pooledKeepProb', [0.5, 0.85, 1])]

        cls.run_thru_data(TextDataReader, dataScale, make_params_dict(params), runScale, useCPU)

    @classmethod
    def full_run(cls, runScale='full', dataScale='full', useCPU=True):
        # ok this is silly. But at least it's fast.
        vocabSize = TextDataReader.maker_from_premade_source(dataScale)(
            bucketingOrRandom='bucketing', batchSize_=50, minimumWords=0).vocabSize

        params = [('initialLearningRate', [1e-3]),
                  ('l2RegLambda', [0, 1e-5]),
                  ('vocabSize', [vocabSize]),
                  ('embeddingDim', [64, 128, 300]),
                  ('filterSizes', [[1, 2, 4], [3, 5, 10, 15]]),
                  ('numFeaturesPerFilter', [16, 32, 64]),
                  ('pooledKeepProb', [0.5, 0.7, 0.9, 1])]

        cls.run_thru_data(TextDataReader, dataScale, make_params_dict(params), runScale, useCPU)

if __name__ == '__main__':
    Mark1.comparison_run()
