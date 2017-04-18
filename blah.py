from pprint import pprint
import logging
from time import time
from datetime import datetime
import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='1'  # Defaults to 0: all logs; 1: filter out INFO logs; 2: filter out WARNING; 3: filter out errors
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow import summary
from tensorflow.python.client.timeline import Timeline
from tensorflow.contrib.rnn import BasicLSTMCell, BasicRNNCell, stack_bidirectional_dynamic_rnn, MultiRNNCell, DropoutWrapper, LSTMCell


from data_reader import DataReader
from utilities import tensorflowFilewriters, setup_logging


DATA_DIR = './data/peopleData/2_samples'
# DATA_DIR = './data/peopleData/earlyLifesWordMats_42B300d/politician_scientist'
# DATA_DIR = './data/peopleData/earlyLifesWordMats'
# DATA_DIR = './data/peopleData/earlyLifesWordMats_42B300d'
PATCH_TO_FULL = False
LOG_DIR = os.path.join('./logs/main', datetime.now().strftime('%m%d%Y %H:%M:%S'))
if not os.path.exists(LOG_DIR): os.mkdir(LOG_DIR)


class Model(object):
    def __init__(self):
        pass

    def assign_lr(self):
        pass

    def train_op(self):
        pass


# sess = tf.InteractiveSession(config=tf.ConfigProto(gpu_options=tf.GPUOptions(per_process_gpu_memory_fraction=0.9)))
sess = tf.InteractiveSession()

# ================== CONFIG ===================

# --------- network ---------
vecDim = 300
# numHiddenLayerFeatures = [128, 128, 64, 32]
# outputKeepProbs = [0.5, 0.7, 0.8, 0.9]
numHiddenLayerFeatures = [32, 16, 8]
outputKeepProbs = [0.5, 0.7, 0.9]
assert len(numHiddenLayerFeatures)==len(outputKeepProbs)

# --------- running ---------
learningRateConstant = 0.002
numSteps = 400  # 1 step runs 1 batch
batchSize = 100

logValidationEvery = 50

# --------- logging ---------
logFilename = os.path.join(LOG_DIR, 'log.log')
setup_logging(logFilename)
configLogger = logging.getLogger('config')
trainLogger = logging.getLogger('run.train')
validateLogger = logging.getLogger('run.validate')
testLogger = logging.getLogger('run.test')
logging.info('Logging to ' + logFilename)

# ================== DATA ===================
with tf.device('/cpu:0'):
    dataReader = DataReader(DATA_DIR, 'bucketing', logFilename)

    numClasses = len(dataReader.get_classes_labels())

    # --------- constant 'variables' ---------
    learningRate = tf.Variable(learningRateConstant, name='learningRate')
    validCost = tf.Variable(1, name='validationCost')
    validAcc = tf.Variable(0, name='validationAccuracy')
    summary.scalar('valid_cost', validCost)
    summary.scalar('valid_accuracy', validAcc)


    def validate_or_test(batchSize_, validateOrTest):

        assert validateOrTest in ['validate', 'test']
        logger = validateLogger if validateOrTest=='validate' else testLogger

        data = dataReader.get_data_in_batches(batchSize_, validateOrTest, patchTofull_=PATCH_TO_FULL)

        totalCost = 0
        totalAccuracy = 0
        allTrueYInds = []
        allPredYInds = []
        allNames = []

        # d: x, y, xLengths, names
        for d in data:

            feedDict = {x: d[0], y: d[1], sequenceLength: d[2]}
            c, acc, trueYInds, predYInds = sess.run([cost, accuracy, trueY, pred], feed_dict=feedDict)

            actualCount = len(d[2])
            totalCost += c * actualCount
            totalAccuracy += acc * actualCount
            allNames += list(d[3])
            allTrueYInds += list(trueYInds)
            allPredYInds += list(predYInds)

        assert len(allTrueYInds)==len(allPredYInds)==len(allNames)

        numDataPoints = len(allTrueYInds)
        avgCost = totalCost / numDataPoints
        avgAccuracy = totalAccuracy / numDataPoints

        # TODO: this doesn't work
        if validateOrTest=='validate':
            sess.run(tf.assign(validCost, avgCost))
            sess.run(tf.assign(validAcc, avgAccuracy))

        logger.info('-------------')
        logger.info(validateOrTest)
        logger.info('loss = %.3f, accuracy = %.3f' % (avgCost, avgAccuracy))
        label_comparison(allTrueYInds, allPredYInds, allNames, logger)
        logger.info('-------------')

    def label_comparison(trueYInds_, predYInds_, names_, logger_):
        labels = dataReader.get_classes_labels()

        logger_.info('True label became... --> ?')

        for i, name in enumerate(names_):
            logger_.info('%-20s %s --> %s %s' % (name, labels[trueYInds_[i]], labels[predYInds_[i]],
                                                 '(wrong)' if trueYInds_[i] != predYInds_[i] else ''))


    def last_relevant(output_, lengths_):
        batch_size = tf.shape(output_)[0]
        max_length = tf.shape(output_)[1]
        out_size = int(output_.get_shape()[2])
        index = tf.range(0, batch_size) * max_length + (lengths_ - 1)
        flat = tf.reshape(output_, [-1, out_size])

        return tf.gather(flat, index)

    def save_matrix_img(mats_, title, outputDir_, transpose_=False):

        d = np.array(mats_) if len(mats_[0].shape) == 1 else np.concatenate(mats_, axis=1)

        fig = plt.figure()
        ax = plt.subplot(111)
        heatmap = ax.matshow(np.transpose(d) if transpose_ else d, cmap='gray')
        plt.colorbar(heatmap)
        plt.title(title)
        fig.savefig(os.path.join(outputDir_, title+'.png'))


    if __name__ == '__main__':
        st = time()

        configLogger.info('SHUFFLED %d hidden layer(s)' % len(numHiddenLayerFeatures))
        configLogger.info('batch size %d, initial learning rate %.3f' % (batchSize, learningRateConstant))
        configLogger.info('number of LSTM cell units: ' + str(numHiddenLayerFeatures))
        configLogger.info('dropoutKeepProbs: ' + str(outputKeepProbs))

        # ================== GRAPH ===================
        x = tf.placeholder(tf.float32, [None, None, vecDim])
        # x = tf.placeholder(tf.float32, [None, dataReader.get_max_len(), vecDim])
        y = tf.placeholder(tf.float32, [None, numClasses])
        sequenceLength = tf.placeholder(tf.int32)

        # weights = tf.Variable(tf.random_normal([numHiddenLayerFeatures, numClasses]))
        weights = tf.Variable(tf.random_normal([2*numHiddenLayerFeatures[-1], numClasses]), name='weights')
        biases = tf.Variable(tf.random_normal([numClasses]), name='biases')

        def make_stacked_cells():

            return [
                DropoutWrapper(BasicLSTMCell(f), output_keep_prob=k) if k < 1 else BasicLSTMCell(f)
                for f, k in zip(numHiddenLayerFeatures, outputKeepProbs)]


        forwardCells = make_stacked_cells()
        backwardCells = make_stacked_cells()

        outputs, _, _ \
            = stack_bidirectional_dynamic_rnn(forwardCells, backwardCells,
                                              inputs=x, dtype=tf.float32,
                                              sequence_length=sequenceLength)


        # outputs = tf.concat(
        #     tf.nn.bidirectional_dynamic_rnn(forwardCells, backwardCells,
        #                                     time_major=False, inputs=x, dtype=tf.float32,
        #                                     sequence_length=sequenceLength,
        #                                     swap_memory=True)[0], 2)


        # cost and optimize
        output = last_relevant(outputs, sequenceLength)
        logits = tf.matmul(output, weights) + biases
        cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=y))
        optimizer = tf.train.AdamOptimizer(learning_rate=learningRateConstant).minimize(cost)

        # predictions and accuracy
        pred = tf.argmax(logits, 1)
        trueY = tf.argmax(y, 1)
        accuracy = tf.reduce_mean(tf.cast(
            tf.equal(pred, trueY)
            , tf.float32))

        summary.scalar('training_cost', cost)
        summary.scalar('training_accuracy', accuracy)

        # =========== set up tensorboard ===========
        merged_summaries = summary.merge_all()
        train_writer, valid_writer = tensorflowFilewriters(LOG_DIR)
        train_writer.add_graph(sess.graph)

        # =========== TRAIN!! ===========
        sess.run(tf.global_variables_initializer())
        dataReader.start_batch_from_beginning()     # technically unnecessary

        # run_metadata = tf.RunMetadata()

        for step in range(numSteps):
            numDataPoints = (step+1) * batchSize

            lrDecay = 0.95 ** (numDataPoints / len(dataReader.train_indices))
            sess.run(tf.assign(learningRate, max(learningRateConstant * lrDecay, 1e-4)))

            batchX, batchY, xLengths, names = dataReader.get_next_training_batch(batchSize, patchTofull_=PATCH_TO_FULL, verbose_=False)
            feedDict = {x: batchX, y: batchY, sequenceLength: xLengths}

            _, summaries, c, acc = sess.run([optimizer, merged_summaries, cost, accuracy], feed_dict=feedDict)
            train_writer.add_summary(summaries, step * batchSize)

            trainLogger.info('Step %d (%d data pts); lr = %0.4f; loss = %.3f, accuracy = %.3f'
                             % (step, numDataPoints, sess.run(learningRate), c, acc))

            # options=tf.RunOptions(trace_level=tf.RunOptions.SOFTWARE_TRACE),
            # run_metadata=run_metadata)
            # trace = Timeline(step_stats=run_metadata.step_stats)

            # print evaluations
            # if step % logTrainingEvery == 0:
            #     summaries, c, acc, trueYInds, predYInds = sess.run([merged_summaries, cost, accuracy, trueY, pred] , feed_dict=feedDict)
            #
            #     train_writer.add_summary(summaries, step * batchSize)
            #     trainLogger.info('loss = %.3f, accuracy = %.3f' % (c, acc))
            #     label_comparison(trueYInds, predYInds, names, trainLogger)

            if step % logValidationEvery == 0:
                # valid_writer.add_summary(summaries, step * batchSize)
                validateLogger.info('Step %d (%d data points); learning rate = %0.4f:' % (step, numDataPoints, sess.run(learningRate)))
                validate_or_test(10, 'validate')


        testLogger.info('Time elapsed: ' + str(time()-st))
        validate_or_test(10, 'test')

        train_writer.close()
        valid_writer.close()

        # trace_file = open('timeline.ctf.json', 'w')
        # trace_file.write(trace.generate_chrome_trace_format())
