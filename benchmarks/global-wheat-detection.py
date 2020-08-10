import os
import sys
import re

import cv2
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

import torch
from torch.utils.data import DataLoader, Dataset
from torch.utils.data.sampler import SequentialSampler
import torchvision
from torchvision import transforms
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection import FasterRCNN
from torchvision.models.detection.rpn import AnchorGenerator

import albumentations as A
from albumentations.pytorch.transforms import ToTensorV2

sys.path.append('../')
from detection import darknet53, Yolov3PredictionHead, Yolov3Model, Yolov3Loss, yolov3_base_darknet_pascal
from detection.utils import AverageMeter


DIR_INPUT = './data/global-wheat-detection'
DIR_TRAIN_IMAGES = os.path.join(DIR_INPUT, 'train')
DIR_VALID_IMAGES = os.path.join(DIR_INPUT, 'valid')
device = 'cuda' if torch.cuda.is_available() else 'cpu'


class WheatDataset(Dataset):
    def __init__(self, df, image_dir, transform=None):
        super().__init__()
        self.df = df
        self.image_ids = df['image_id'].unique()
        self.image_dir = image_dir
        self.transform = transform
             
    def __getitem__(self, index: int):
        image_id = self.image_ids[index]
        records = self.df[self.df['image_id'] == image_id]

        image = cv2.imread(os.path.join(self.image_dir, f'{image_id}.jpg'), cv2.IMREAD_COLOR)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32)
        image /= 255.0

        boxes = records[['x', 'y', 'w', 'h']].values.astype(np.int32)
        boxes[:, 2] = boxes[:, 0] + boxes[:, 2]
        boxes[:, 3] = boxes[:, 1] + boxes[:, 3]
        
        area = (boxes[:, 3] - boxes[:, 1]) * (boxes[:, 2] - boxes[:, 0])
        area = torch.as_tensor(area, dtype=torch.float32)
        # there is only one class
        labels = torch.ones((records.shape[0],), dtype=torch.int64)
        # suppose all instances are not crowd
        iscrowd = torch.zeros((records.shape[0],), dtype=torch.int64)
        
        target = {
            'image_id': torch.tensor([index]),
            'boxes': boxes,
            'labels': labels,
            'area': area,
            'iscrowd': iscrowd
        }
        if self.transform:
            sample = {
                'image': image,
                'bboxes': boxes,
                'labels': labels,
            }
            sample = self.transform(**sample)
            image = sample['image']
            target['boxes'] = torch.tensor(sample['bboxes'])
        
        return image, target

    def __len__(self) -> int:
        return len(self.image_ids)


def get_transform(train=True):
    return A.Compose([
        ToTensorV2(p=1.0)], 
        bbox_params={
            'format': 'pascal_voc', 
            'label_fields': ['labels']})


train_labels = pd.read_csv(os.path.join(DIR_INPUT, 'train_labels.csv'))
valid_labels = pd.read_csv(os.path.join(DIR_INPUT, 'valid_labels.csv'))

trainset = WheatDataset(train_labels, DIR_TRAIN_IMAGES, get_transform())
validset = WheatDataset(valid_labels, DIR_VALID_IMAGES, get_transform())

def collate_fn(batch):
    return tuple(zip(*batch))

train_loader = DataLoader(
    trainset,
    batch_size=2,
    shuffle=False,
    num_workers=4,
    collate_fn=collate_fn)

valid_loader = DataLoader(
    validset,
    batch_size=8,
    shuffle=False,
    num_workers=4,
    collate_fn=collate_fn)


# load a model; pre-trained on COCO
model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
num_classes = 2  # 1 class (wheat) + background
# get number of input features for the classifier
in_features = model.roi_heads.box_predictor.cls_score.in_features
# replace the pre-trained head with a new one
model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
model.to(device)
params = [p for p in model.parameters() if p.requires_grad]
optimizer = torch.optim.SGD(params, lr=0.005, momentum=0.9, weight_decay=0.0005)




num_epochs = 2
loss_hist = AverageMeter()
itr = 1
# sys.exit(0)
model.train()
for epoch in range(num_epochs):
    for images, targets in train_loader:
        images = [image.to(device) for image in images]
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        # print(targets[0]['boxes'])

        loss_dict = model(images, targets)
        # print(len(outputs))
        # print(outputs[0]['boxes'].size())
        # print(outputs[0]['boxes'].view(2, -1, 4).size())

        # losses = criterion(outputs, targets)
        



        
        
        losses = sum(loss for loss in loss_dict.values())
        loss_value = losses.item()

        loss_hist.update(loss_value)

        optimizer.zero_grad()
        losses.backward()
        optimizer.step()

    
    print(f"Epoch #{epoch} loss: {losses}")   

sys.exit(0)

images, targets = next(iter(valid_loader))
images = list(img.to(device) for img in images)
targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

boxes = targets[1]['boxes'].cpu().numpy().astype(np.int32)
sample = images[1].permute(1,2,0).cpu().numpy()

model.eval()
cpu_device = torch.device("cpu")

outputs = model(images)
print(outputs)
outputs = [{k: v.to(cpu_device) for k, v in t.items()} for t in outputs]



fig, ax = plt.subplots(1, 1, figsize=(16, 8))

for box in boxes:
    cv2.rectangle(sample,
                  (box[0], box[1]),
                  (box[2], box[3]),
                  (220, 0, 0), 3)
    
ax.set_axis_off()
ax.imshow(sample)
plt.show()

torch.save(model.state_dict(), 'fasterrcnn_resnet50_fpn.pth')