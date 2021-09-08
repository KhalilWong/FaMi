import gfootball.env as football_env
import time, os
import numpy as np
import torch

################################################################################
def save_args(arg_dict):
    os.makedirs(arg_dict['log_dir'])
    with open(arg_dict['log_dir'] + '/args.json', 'w') as out:
        json.dump(arg_dict, indent = 4, out)

################################################################################
def main(arg_dict):
    os.environ['OPENBLAS_NUM_THREADS'] = '1'#???
    cur_time = datetime.now()
    arg_dict['log_dir'] = 'logs/' + cur_time.strftime('[%m-%d]%H.%M.%S')
    save_args(arg_dict)
    #
    np.set_printoptions(precision = 3)
    np.set_printoptions(suppress = True)
    pp = pprint.PrettyPrinter(indent = 4)
    torch.set_num_threads(1)

    fe = importlib.import_module("encoders." + arg_dict["encoder"])
    fe = fe.FeatureEncoder()
    arg_dict["feature_dims"] = fe.get_feature_dims()

    model = importlib.import_module("models." + arg_dict["model"])
    cpu_device = torch.device('cpu')
    center_model = model.Model(arg_dict)

    if arg_dict["trained_model_path"]:
        checkpoint = torch.load(arg_dict["trained_model_path"], map_location=cpu_device)
        optimization_step = checkpoint['optimization_step']
        center_model.load_state_dict(checkpoint['model_state_dict'])
        center_model.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        arg_dict["optimization_step"] = optimization_step
        print("Trained model", arg_dict["trained_model_path"] ,"suffessfully loaded")
    else:
        optimization_step = 0

    model_dict = {
        'optimization_step': optimization_step,
        'model_state_dict': center_model.state_dict(),
        'optimizer_state_dict': center_model.optimizer.state_dict(),
    }

    path = arg_dict["log_dir"]+f"/model_{optimization_step}.tar"
    torch.save(model_dict, path)

    center_model.share_memory()
    data_queue = mp.Queue()
    signal_queue = mp.Queue()
    summary_queue = mp.Queue()

    processes = []
    p = mp.Process(target=learner, args=(center_model, data_queue, signal_queue, summary_queue, arg_dict))
    p.start()
    processes.append(p)
    for rank in range(arg_dict["num_processes"]):
        if arg_dict["env"] == "11_vs_11_kaggle":
            p = mp.Process(target=actor_self, args=(rank, center_model, data_queue, signal_queue, summary_queue, arg_dict))
        else:
            p = mp.Process(target=actor, args=(rank, center_model, data_queue, signal_queue, summary_queue, arg_dict))
        p.start()
        processes.append(p)

    if "env_evaluation" in arg_dict:
        p = mp.Process(target=evaluator, args=(center_model, signal_queue, summary_queue, arg_dict))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

################################################################################
if __name__ == '__main__':
    arg_dict = {
        'env': '11_vs_11_kaggle',
        # '11_vs_11_kaggle' : environment used for self-play training
        # '11_vs_11_stochastic' : environment used for training against fixed opponent(rule-based AI)
        'env_evaluation': '11_vs_11_hard_stochastic',  # for evaluation of self-play trained agent (like validation set in Supervised Learning)
        #
        'model': 'conv1d',
        'algorithm': 'ppo'
    }
    main(arg_dict)