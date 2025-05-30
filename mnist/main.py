import torch
import torch.nn as nn
import torch.optim as optim
# I'm here again

import argparse
import os

import time

from model import Model
from preprocess import load_data
from mnistmodel import *
# from models.vgg import VGG
# from models.mobilenet import MobileNet
# from models.mobilenetv2 import MobileNetV2
# from models.shufflenetv2 import ShuffleNetV2


use_cuda = torch.cuda.is_available()
device = torch.device("cuda" if use_cuda else "cpu")


def adjust_learning_rate(optimizer, epoch, args):
    """Sets the learning rate to the initial LR decayed by 10 every 30 epochs"""
    lr = args.learning_rate * (0.1 ** (epoch // 30))
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr


def train(model, train_loader, optimizer, criterion, epoch, args):
    model.train()
    step = 0
    train_loss = 0
    train_acc = 0
    for data, target in train_loader:
        adjust_learning_rate(optimizer, epoch, args)
        data, target = data.to(device), target.to(device)

        optimizer.zero_grad()
        output = model(data)
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()
        train_loss += loss.data
        y_pred = output.data.max(1)[1]

        acc = float(y_pred.eq(target.data).sum()) / len(data) * 100.
        train_acc += acc
        step += 1
        if step % 100 == 0:
            print("[Epoch {0:4d}] Loss: {1:2.3f} Acc: {2:.3f}%".format(epoch, loss.data, acc), end='')
            for param_group in optimizer.param_groups:
                print(",  Current learning rate is: {}".format(param_group['lr']))

    length = len(train_loader.dataset) // args.batch_size
    return train_loss / length, train_acc / length


def get_test(model, test_loader):
    model.eval()
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            prediction = output.data.max(1)[1]
            correct += prediction.eq(target.data).sum()

    acc = 100. * float(correct) / len(test_loader.dataset)
    return acc


def main():
    parser = argparse.ArgumentParser('parameters')

    parser.add_argument('--epochs', type=int, default=100, help='number of epochs, (default: 100)')
    parser.add_argument('--p', type=float, default=0.75, help='graph probability, (default: 0.75)')
    parser.add_argument('--c', type=int, default=78, help='channel count for each node, (example: 78, 157, 267), (default: 78)')
    parser.add_argument('--k', type=int, default=4, help='each node is connected to k nearest neighbors in ring topology, (default: 4)')
    parser.add_argument('--m', type=int, default=5, help='number of edges to attach from a new node to existing nodes, (default: 5)')
    parser.add_argument('--graph-mode', type=str, default="NCNN", help="random graph, (Example: NCNN, ER, WS, BA), (default: NCNN)")
    parser.add_argument('--graph-type', type=str, default="ncnn16.xlsx", help="adjacency matrix end with '.xlsx', (Example: ncnn16.xlsx, ncnn18.xlsx), (default: ncnn.xlsx)")
    parser.add_argument('--arch', '-a', default='ResNet18', type=str)
    parser.add_argument('--node-num', type=int, default=16, help="Number of graph node (default n=16)")
    parser.add_argument('--learning-rate', type=float, default=1e-1, help='learning rate, (default: 1e-1)')
    parser.add_argument('--batch-size', type=int, default=128, help='batch size, (default: 128)')
    parser.add_argument('--dataset-mode', type=str, default="MNIST", help='Which dataset to use? (Example, CIFAR10, CIFAR100, MNIST), (default: CIFAR10)')
    parser.add_argument('--is-train', type=bool, default=True, help="True if training, False if test. (default: True)")
    parser.add_argument('--load-model', type=bool, default=False)

    args = parser.parse_args()

    train_loader, test_loader = load_data(args)

    if args.load_model:
        model = Model(args.node_num, args.p, args.c, args.c, args.graph_mode, args.graph_type, args.dataset_mode, args.is_train).to(device)
        filename = "graph_mode_" + args.graph_mode + "_graph_type_" + args.graph_type + "_node_num_" + str(args.node_num)  + "_dataset_" + args.dataset_mode
        checkpoint = torch.load('./checkpoint/' + filename + 'ckpt.t7')
        model.load_state_dict(checkpoint['model'])
        epoch = checkpoint['epoch']
        acc = checkpoint['acc']
        print("Load Model Accuracy: ", acc, "Load Model end epoch: ", epoch)
    else:
        # model = Model(args.node_num, args.p, args.c, args.c, args.graph_mode, args.graph_type, args.dataset_mode, args.is_train).to(device)
        if args.arch == "r18":
            model = resnet18()
        elif args.arch == "r34":
            model = resnet34()
        elif args.arch == "r34":
            model = resnet34()
        elif args.arch == "r50":
            model = resnet50()
        elif args.arch == "r101":
            model = resnet101()
        elif args.arch == "r152":
            model = resnet152()
        elif args.arch == "m":
            model = mobilenet()
        elif args.arch == "mv2":
            model = mobilenetv2()
        elif args.arch == "iv3":
            model = inceptionv3()
        elif args.arch == "pr18":
            model = preactresnet18()
        elif args.arch == "pr34":
            model = preactresnet34()
        elif args.arch == "pr50":
            model = preactresnet50()
        elif args.arch == "pr101":
            model = preactresnet101()
        elif args.arch == "pr152":
            model = preactresnet152()
        elif args.arch == "googlenet":
            model = googlenet()
        else:
            raise ValueError("Unknown architecture")
        model = model.to(device)
        if device == 'cuda':
            model = torch.nn.DataParallel(model)
            cudnn.benchmark = True

    if torch.cuda.device_count() > 1:
        print("Let's use", torch.cuda.device_count(), "GPUs!")
        model = torch.nn.DataParallel(model)
    optimizer = torch.optim.SGD(model.parameters(), lr=args.learning_rate, weight_decay=5e-4, momentum=0.9)
    criterion = nn.CrossEntropyLoss().to(device)

    epoch_list = []
    test_acc_list = []
    train_acc_list = []
    train_loss_list = []
    max_test_acc = 0
    if not os.path.isdir("reporting"):
        os.mkdir("reporting")

    start_time = time.time()
    with open("./reporting/" + "graph_mode_" + args.graph_mode + "_graph_type_" + args.graph_type + "_node_num_" + str(args.node_num)  + "_dataset_" + args.dataset_mode + str(args.c) + ".txt", "w") as f:
        for epoch in range(1, args.epochs + 1):
            # scheduler = CosineAnnealingLR(optimizer, epoch)
            epoch_list.append(epoch)
            train_loss, train_acc = train(model, train_loader, optimizer, criterion, epoch, args)
            test_acc = get_test(model, test_loader)
            test_acc_list.append(test_acc)
            train_loss_list.append(train_loss)
            train_acc_list.append(train_acc)
            print('Test set accuracy: {0:.2f}%, Best accuracy: {1:.2f}%'.format(test_acc, max_test_acc))
            f.write("[Epoch {0:3d}] Test set accuracy: {1:.3f}%, , Best accuracy: {2:.2f}%".format(epoch, test_acc, max_test_acc))
            f.write("\n ")

            if max_test_acc < test_acc:
                print('Saving..')
                state = {
                    'model': model.state_dict(),
                    'acc': test_acc,
                    'epoch': epoch,
                }
                if not os.path.isdir('checkpoint'):
                    os.mkdir('checkpoint')
                filename = args.graph_mode + "_graph_type_" + args.graph_type + "_node_num_" + str(args.node_num)  + "_dataset_" + args.dataset_mode
                torch.save(state, './checkpoint/' + filename + 'ckpt.t7')
                max_test_acc = test_acc
                
            print("Training time: ", time.time() - start_time)
            f.write("Training time: " + str(time.time() - start_time))
            f.write("\n")


if __name__ == '__main__':
    main()
