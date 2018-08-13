from __future__ import absolute_import
from __future__ import print_function

from pyspark.mllib.linalg import Matrix, Vector

from .utils.rdd_utils import lp_to_simple_rdd
from .utils.serialization import model_to_dict
from .mllib.adapter import to_matrix, from_matrix, to_vector, from_vector
from .optimizers import SGD as default_optimizer
from .worker import AsynchronousSparkWorker, SparkWorker
from .parameter.server import HttpServer, SocketServer
from .parameter.connector import HttpConnector, SocketConnector


class SparkModel(object):
    '''
    SparkModel is the main abstraction of elephas. Every other model
    should inherit from it.
    '''
    # TODO: Eliminate Spark context (only used for first broadcast, can be extracted)
    def __init__(self, sc, master_network, optimizer=None,
                 mode='asynchronous', frequency='epoch',
                 num_workers=4,
                 master_optimizer="sgd",  # TODO: other default
                 master_loss="categorical_crossentropy",
                 master_metrics=None,
                 custom_objects=None,
                 parameter_server='http',
                 *args, **kwargs):

        self.spark_context = sc
        self._master_network = master_network
        if custom_objects is None:
            custom_objects = {}
        if master_metrics is None:
            master_metrics = ["accuracy"]
        if optimizer is None:
            self.optimizer = default_optimizer()
        else:
            self.optimizer = optimizer
        self.mode = mode
        self.frequency = frequency
        self.num_workers = num_workers
        self.weights = master_network.get_weights()
        self.pickled_weights = None
        self.master_optimizer = master_optimizer
        self.master_loss = master_loss
        self.master_metrics = master_metrics
        self.custom_objects = custom_objects

        # TODO: connector has to be initialized on workers
        if parameter_server == 'http':
            self.parameter_server = HttpServer(self.master_network, self.optimizer, self.mode)
            self.connector = HttpConnector()
        else:
            self.parameter_server = SocketServer(model_to_dict(self.master_network))
            self.connector = SocketConnector()

    def get_train_config(self, nb_epoch, batch_size,
                         verbose, validation_split):
        '''
        Get configuration of training parameters
        '''
        train_config = {}
        train_config['nb_epoch'] = nb_epoch
        train_config['batch_size'] = batch_size
        train_config['verbose'] = verbose
        train_config['validation_split'] = validation_split
        return train_config

    def get_config(self):
        '''
        Get configuration of model parameters
        '''
        model_config = {}
        model_config['model'] = self.master_network.get_config()
        model_config['optimizer'] = self.optimizer.get_config()
        model_config['mode'] = self.mode
        return model_config

    @property
    def master_network(self):
        return self._master_network

    @master_network.setter
    def master_network(self, network):
        self._master_network = network

    def start_server(self):
        self.parameter_server.start()

    def stop_server(self):
<<<<<<< HEAD
        self.parameter_server.stop()
=======
        ''' Terminate parameter server'''
        self.server.terminate()
        self.server.join()

    def start_service(self):
        ''' Define service and run flask app'''
        app = Flask(__name__)
        self.app = app

        @app.route('/')
        def home():
            return 'Elephas'

        @app.route('/parameters', methods=['GET'])
        def get_parameters():
            if self.mode == 'asynchronous':
                self.lock.acquire_read()
            self.pickled_weights = pickle.dumps(self.weights, -1)
            pickled_weights = self.pickled_weights
            if self.mode == 'asynchronous':
                self.lock.release()
            return pickled_weights

        @app.route('/update', methods=['POST'])
        def update_parameters():
            delta = pickle.loads(request.data)
            if self.mode == 'asynchronous':
                self.lock.acquire_write()

            if not self.master_network.built:
                self.master_network.build()

            base_constraint = lambda a: a
            constraints = [base_constraint for x in self.weights]

            self.weights = self.optimizer.get_updates(self.weights, constraints, delta)

            if self.mode == 'asynchronous':
                self.lock.release()

            return 'Update done'

        self.app.run(host='0.0.0.0', debug=True,
                     threaded=True, use_reloader=False)
>>>>>>> master

    def predict(self, data):
        '''Get prediction probabilities for a numpy array of features
        '''
        return self.master_network.predict(data)

    def predict_classes(self, data):
        '''Predict classes for a numpy array of features
        '''
        return self.master_network.predict_classes(data)

    def train(self, rdd, nb_epoch=10, batch_size=32,
              verbose=0, validation_split=0.1):
        # TODO: Make dataframe the standard, but support RDDs as well
        '''Train an elephas model.
        '''
        rdd = rdd.repartition(self.num_workers)

        if self.mode in ['asynchronous', 'synchronous', 'hogwild']:
            self._train(rdd, nb_epoch, batch_size, verbose, validation_split)
        else:
            raise Exception("""Choose from one of the modes: asynchronous, synchronous or hogwild""")

    def _train(self, rdd, nb_epoch=10, batch_size=32, verbose=0,
               validation_split=0.1):
        '''
        Protected train method to make wrapping of modes easier
        '''
        self.master_network.compile(optimizer=self.master_optimizer,
                                    loss=self.master_loss,
                                    metrics=self.master_metrics)
        if self.mode in ['asynchronous', 'hogwild']:
            self.start_server()
        yaml = self.master_network.to_yaml()
        train_config = self.get_train_config(nb_epoch, batch_size,
                                             verbose, validation_split)
        if self.mode in ['asynchronous', 'hogwild']:
            worker = AsynchronousSparkWorker(
                yaml, self.connector, train_config, self.frequency,
                self.master_optimizer, self.master_loss, self.master_metrics, self.custom_objects
            )
            rdd.mapPartitions(worker.train).collect()
            new_parameters = self.connector.get_parameters()
        elif self.mode == 'synchronous':
            init = self.master_network.get_weights()
            parameters = self.spark_context.broadcast(init)
            worker = SparkWorker(
                yaml, parameters, train_config, 
                self.master_optimizer, self.master_loss, self.master_metrics, self.custom_objects
            )
            deltas = rdd.mapPartitions(worker.train).collect()
            new_parameters = self.master_network.get_weights()
            for delta in deltas:
                constraints = self.master_network.constraints
                new_parameters = self.optimizer.get_updates(self.weights, constraints, delta)
        self.master_network.set_weights(new_parameters)
        if self.mode in ['asynchronous', 'hogwild']:
            self.stop_server()


<<<<<<< HEAD
=======
class SparkWorker(object):
    '''
    Synchronous Spark worker. This code will be executed on workers.
    '''
    def __init__(self, yaml, parameters, train_config, master_optimizer, master_loss, master_metrics, custom_objects):
        self.yaml = yaml
        self.parameters = parameters
        self.train_config = train_config
        self.master_optimizer = master_optimizer
        self.master_loss = master_loss
        self.master_metrics = master_metrics
        self.custom_objects = custom_objects

    def train(self, data_iterator):
        '''
        Train a keras model on a worker
        '''
        feature_iterator, label_iterator = tee(data_iterator, 2)
        x_train = np.asarray([x for x, y in feature_iterator])
        y_train = np.asarray([y for x, y in label_iterator])

        model = model_from_yaml(self.yaml, self.custom_objects)
        model.compile(optimizer=self.master_optimizer, loss=self.master_loss, metrics=self.master_metrics)
        model.set_weights(self.parameters.value)
        weights_before_training = model.get_weights()
        if x_train.shape[0] > self.train_config.get('batch_size'):
            model.fit(x_train, y_train, **self.train_config)
        weights_after_training = model.get_weights()
        deltas = subtract_params(weights_before_training, weights_after_training)
        yield deltas


class AsynchronousSparkWorker(object):
    '''
    Asynchronous Spark worker. This code will be executed on workers.
    '''
    def __init__(self, yaml, train_config, frequency, master_url, master_optimizer, master_loss, master_metrics, custom_objects):
        self.yaml = yaml
        self.train_config = train_config
        self.frequency = frequency
        self.master_url = master_url
        self.master_optimizer = master_optimizer
        self.master_loss = master_loss
        self.master_metrics = master_metrics
        self.custom_objects = custom_objects


    def train(self, data_iterator):
        '''
        Train a keras model on a worker and send asynchronous updates
        to parameter server
        '''
        feature_iterator, label_iterator = tee(data_iterator, 2)
        x_train = np.asarray([x for x, y in feature_iterator])
        y_train = np.asarray([y for x, y in label_iterator])

        if x_train.size == 0:
            return

        model = model_from_yaml(self.yaml, self.custom_objects)
        model.compile(optimizer=self.master_optimizer, loss=self.master_loss, metrics=self.master_metrics)

        nb_epoch = self.train_config['nb_epoch']
        batch_size = self.train_config.get('batch_size')
        nb_train_sample = x_train.shape[0]
        nb_batch = int(np.ceil(nb_train_sample/float(batch_size)))
        index_array = np.arange(nb_train_sample)
        batches = [(i*batch_size, min(nb_train_sample, (i+1)*batch_size)) for i in range(0, nb_batch)]

        if self.frequency == 'epoch':
            for epoch in range(nb_epoch):
                weights_before_training = get_server_weights(self.master_url)
                model.set_weights(weights_before_training)
                self.train_config['epochs'] = 1
                self.train_config['nb_epoch'] = 1
                if x_train.shape[0] > batch_size:
                    model.fit(x_train, y_train, **self.train_config)
                self.train_config['nb_epoch'] = nb_epoch
                weights_after_training = model.get_weights()
                deltas = subtract_params(weights_before_training, weights_after_training)
                put_deltas_to_server(deltas, self.master_url)
        elif self.frequency == 'batch':
            from keras.engine.training import slice_X
            for epoch in range(nb_epoch):
                if x_train.shape[0] > batch_size:
                    for (batch_start, batch_end) in batches:
                        weights_before_training = get_server_weights(self.master_url)
                        model.set_weights(weights_before_training)
                        batch_ids = index_array[batch_start:batch_end]
                        X = slice_X(x_train, batch_ids)
                        y = slice_X(y_train, batch_ids)
                        model.train_on_batch(X, y)
                        weights_after_training = model.get_weights()
                        deltas = subtract_params(weights_before_training, weights_after_training)
                        put_deltas_to_server(deltas, self.master_url)
        else:
            print('Choose frequency to be either batch or epoch')
        yield []


>>>>>>> master
class SparkMLlibModel(SparkModel):
    '''
    MLlib model takes RDDs of LabeledPoints. Internally we just convert
    back to plain old pair RDDs and continue as in SparkModel
    '''
    def __init__(self, sc, master_network, optimizer=None, mode='asynchronous', frequency='epoch', num_workers=4,
                 master_optimizer="adam",
                 master_loss="categorical_crossentropy",
                 master_metrics=None,
                 custom_objects=None):
        SparkModel.__init__(self, sc, master_network, optimizer, mode, frequency, num_workers,
                            master_optimizer=master_optimizer, master_loss=master_loss, master_metrics=master_metrics,
                            custom_objects=custom_objects)

    def train(self, labeled_points, nb_epoch=10, batch_size=32, verbose=0, validation_split=0.1,
              categorical=False, nb_classes=None):
        '''
        Train an elephas model on an RDD of LabeledPoints
        '''
        rdd = lp_to_simple_rdd(labeled_points, categorical, nb_classes)
        rdd = rdd.repartition(self.num_workers)
        self._train(rdd, nb_epoch, batch_size, verbose, validation_split)

    def predict(self, mllib_data):
        '''
        Predict probabilities for an RDD of features
        '''
        if isinstance(mllib_data, Matrix):
            return to_matrix(self.master_network.predict(from_matrix(mllib_data)))
        elif isinstance(mllib_data, Vector):
            return to_vector(self.master_network.predict(from_vector(mllib_data)))
        else:
            print('Provide either an MLLib matrix or vector')
