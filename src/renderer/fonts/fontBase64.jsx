import * as Arias from "./arial";
import * as Simli from "./SIMLI";
import * as Simhei from "./simhei";
import * as Simkai from "./simkai";
import * as Time from "./times";
import * as Schei from "./schei";
import * as Scsong from "./scsong";
export const fontBase64Map = {
  'arial': {
		family:'arial',
    label: "Arial",
		weights:{
      normal:{
        base64:Arias.normalBase64,
        ttf:'./arial.ttf',
        weight:"normal",
      },
    }
  },
	'simhei':{
		family:'simhei',
    label: "黑体",
		weights:{
      normal:{
        base64:Simhei.normalBase64,
        ttf:'./simhei.ttf',
        weight:"normal",
      },
    }
  }, 
    'simkai': {
      family:'simkai',
      label: "楷体",
      weights:{
        normal:{
          base64:Simkai.normalBase64,
          ttf:'./simkai.ttf',
          weight:"normal",
        },
      }
    },
    'SIMLI': {
      family:'SIMLI',
      label: "隶书",
      weights:{
        normal:{
          base64:Simli.normalBase64,
          ttf:'./SIMLI.ttf',
          weight:"normal",
        },
      }
    },

    'times': {
      family:'times',
      label: "Times New Roman",
      weights:{
        normal:{
          base64:Time.normalBase64,
          ttf:'./times.ttf',
          weight:"normal",
        },
      }
    },
      'scsong':{
        family:'scsong',
        label: "思源宋体",
        weights:{
          normal:{
            base64:Scsong.normalBase64,
            ttf:'./scsong.ttf',
            weight:"normal",
          },
          bold:{
            base64:Scsong.boldBase64,
            ttf:'./scsong-bold.ttf',
            weight:"bold",
          },
        }
      },
      'schei':{
        family:'schei',
        label: "思源黑体",
        weights:{
          normal:{
            base64:Schei.normalBase64,
            ttf:'./schei.ttf',
            weight:"normal",
          },
          bold:{
            base64:Schei.boldBase64,
            ttf:'./schei-bold.ttf',
            weight:"bold",
          },
        }
      },
  
  };