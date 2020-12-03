
import sys
from typing import Tuple, List, Dict, Any
import numpy as np
import torch
from torch import nn, Tensor

from .architecture_base import BaseModel
from .backbone_darknet import darknet21


class Yolov1PredictNeck(nn.Module):
    """Prediction Neck for YOLOv1
    Arguments:
        in_channels (int): 
    """
    def __init__(self, config, in_channels: int, **kwargs) -> None:
        """
        """
        super().__init__()
        self.config = config
        self.layers = nn.Sequential(
            nn.Conv2d(in_channels, 1024, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(1024, 1024, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(1024, 1024, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(1024, 1024, kernel_size=3, padding=1),
            nn.ReLU())
    
    def forward(self, inputs: List[Tensor]) -> Tensor:
        """
            inputs (List[Tensor]): 
        
        Return:
            (Tensor): Size([])
        """
        return self.layers(inputs[self.config.selected_layers])
    

class Yolov1PredictHead(nn.Module):
    """Prediction Neck for YOLOv1
    Arguments:
        selected_layers (List[float]):
        scales (List[float]):
    """
    def __init__(self, config, **kwargs) -> None:
        super().__init__()
        self.config = config
        self.out_channels = 5 * config.num_boxes + config.num_classes
        self.layers = nn.Sequential(
            nn.Linear(config.grid_size * config.grid_size * 1024, 4096),
            nn.ReLU(),
            nn.Linear(4096, config.grid_size * config.grid_size * self.out_channels),
            nn.Sigmoid())
        # self._initialize_weights()

    def forward(self, inputs: Tensor) -> Dict[str, Tensor]:
        """
        Argument:
            inputs (Tensor): Size([])
        Return:
            Dict[str, Tensor]:
                boxes: Size([batch_size, num_boxes, 4])
                scores: Size([batch_size, num_boxes])
                labels: Size([batch_size, num_boxes, 20])
        """
        bs = inputs.size(0)
        inputs = inputs.view(bs, -1)
        outputs = self.layers(inputs)        
        outputs = outputs.view(-1, self.config.grid_size, self.config.grid_size, self.out_channels)
        outputs = outputs.view(bs, -1, 5*self.config.num_boxes+self.config.num_classes)

        boxes = outputs[..., :5*self.config.num_boxes].contiguous().view(bs, -1, 5)        
        scores = boxes[..., 4]
        boxes = boxes[..., :4]
        labels = outputs[..., 5*self.config.num_boxes:]
        labels = labels.repeat(1, 2, 1)
    
        preds = {
            'boxes': boxes,
            'scores': scores,
            'labels': labels}
        
        return preds
        

class Yolov1Pretrained(BaseModel):
    def __init__(self):
        super().__init__()
        pass
    # def _init_weights(self, module):
    #     """ Initialize the weights """
    #     if isinstance(module, (nn.Linear, nn.Embedding)):
    #         # Slightly different from the TF version which uses truncated_normal for initialization
    #         # cf https://github.com/pytorch/pytorch/pull/5617
    #         module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)
    #     elif isinstance(module, nn.LayerNorm):
    #         module.bias.data.zero_()
    #         module.weight.data.fill_(1.0)
    #     if isinstance(module, nn.Linear) and module.bias is not None:
    #         module.bias.data.zero_()


class Yolov1Model(Yolov1Pretrained):
    """
    ██╗   ██╗ ██████╗ ██╗      ██████╗           ████╗ 
    ╚██╗ ██╔╝██╔═══██╗██║     ██╔═══██╗          ╚═██║
     ╚████╔╝ ██║   ██║██║     ██║   ██║██╗   ██╗   ██║
      ╚██╔╝  ██║   ██║██║     ██║   ██║╚██╗ ██╔╝   ██║
       ██║   ╚██████╔╝███████╗╚██████╔╝ ╚████╔╝  ██████╗
       ╚═╝    ╚═════╝ ╚══════╝ ╚═════╝   ╚═══╝   ╚═════╝

    The only specificity that we require is that the dataset 
    __getitem__ should return:

    Arguments:
        image: a PIL Image of size (H, W)
        target: a dict containing the following fields
            boxes (FloatTensor[N, 4]): the coordinates of the N bounding boxes 
                in [x0, y0, x1, y1] format, ranging from 0 to W and 0 to H
            labels (Int64Tensor[N]): the label for each bounding box. 0 represents 
                always the background class.
            image_id (Int64Tensor[1]): an image identifier. It should be unique 
                between all the images in the dataset, and is used during evaluation
            area (Tensor[N]): The area of the bounding box. This is used during 
                evaluation with the COCO metric, to separate the metric scores between small, medium and large boxes.
            iscrowd (UInt8Tensor[N]): instances with iscrowd=True will be ignored 
                during evaluation.
    """
    def __init__(self, config, backbone=None, neck=None, head=None, **kwargs) -> None:
        super().__init__()
        self.config = config
        if backbone is None:
            self.backbone = darknet21(pretrained=False)
        if neck is None:
            self.neck = Yolov1PredictNeck(config, self.backbone.channels[-1])
        if head is None:
            self.head = Yolov1PredictHead(config)

        # self._init_weights()

    def forward(self, inputs: List[Tensor]) -> List[Tensor]:
        """
        Argument:
            inputs (List(FloatTensor[C, H, W]): Number of batch size Size([B, C, H, W]))
        Return:
            outputs
        """
        if self.training:
            inputs = self.check_inputs(inputs)
            outputs = self.backbone(inputs)
            outputs = self.neck(outputs)
            outputs = self.head(outputs)

            return outputs
        else:
            return inputs

    


    