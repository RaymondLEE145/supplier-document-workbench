(window["webpackJsonp"] = window["webpackJsonp"] || []).push([["chunk-a1338fd0"],{

/***/ "1b62":
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* WEBPACK VAR INJECTION */(function(process) {/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return mixinCommon; });
/* harmony import */ var _api_user__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__("fab2");

const mixinCommon = {
  data() {
    return {
      // 页面开始加载时间
      PAGE_LOAD_START_TIME: "",
      // 页面渲染完成时间
      PAGE_LOAD_END_TIME: ""
    };
  },
  created() {
    this.PAGE_LOAD_START_TIME = new Date().getTime();
  },
  async mounted() {
    // 获取加载时间
    this.PAGE_LOAD_END_TIME = new Date().getTime();
    this.GET_PAGE_LOG();
    // 刷新时，删除sessionStorage中记录的页面，防止刷新后不进行日志统计功能
    if (process.client) {
      window.addEventListener('beforeunload', () => {
        sessionStorage.removeItem('currentLogePage');
      });
    }
  },
  methods: {
    // 获取页面统计信息
    GET_PAGE_LOG() {
      let origin = "";
      if (process.client) {
        origin = window.location.origin;
      }
      // let params = {
      //     loadTime: this.PAGE_LOAD_END_TIME - this.PAGE_LOAD_START_TIME,
      //     curl: `${this.$nuxt.context.base}${this.$route.fullPath}`.replace('//', '/'),
      //     refererUrl: `${origin}${this.$nuxt.context.base}${this.$nuxt.context.from ? this.$nuxt.context.from.fullPath : ''}`,
      //     pageCode: this.$route.name.toUpperCase(),
      //     screen: `${document.documentElement.clientWidth} * ${document.documentElement.clientHeight}`
      // }
      // oneStopService  取id
      let params = {
        loadTime: this.PAGE_LOAD_END_TIME - this.PAGE_LOAD_START_TIME,
        curl: `${this.$route.fullPath}`.replace('//', '/'),
        refererUrl: `${origin}${this.$route.from ? this.$route.from.fullPath : ''}`,
        pageCode: this.$route.name === 'oneStopService' ? this.$route.query.id.toUpperCase() : this.$route.name.toUpperCase(),
        screen: `${document.documentElement.clientWidth} * ${document.documentElement.clientHeight}`
      };
      let refererUrl = sessionStorage.getItem('refererUrl');
      if (!refererUrl) {
        const referrer = document.referrer;
        params.refererUrl = referrer;
        sessionStorage.setItem('refererUrl', refererUrl);
      }
      Object(_api_user__WEBPACK_IMPORTED_MODULE_0__[/* getPageLog */ "b"])(params);
      // （后端日志代码已复制到ocisweb，页面加载日志接口路径/ociswebserver/AccessLog/pageLog）
      //     接口参数：{
      //     "loadTime":"页面加载时间",
      //     "curl":"当前地址栏url",
      //     "refererUrl":"页面来源url",
      //     "pageCode":"页面编码",
      //     "screen":"屏幕分辨率"
      // }

      // 通过sessionstorate中记录当前发送日志统计的页面，防止重复执行(办事指南页面需要每次点击都统计)
      // let currentLogePage = sessionStorage.getItem('currentLogePage');
      // if (!currentLogePage || currentLogePage != params.curl || currentLogePage.indexOf('/treeGuide') != -1) {
      //     sessionStorage.setItem('currentLogePage', params.curl)
      //     getPageLog(params)
      // }
    }
  }
};
/* WEBPACK VAR INJECTION */}.call(this, __webpack_require__("4362")))

/***/ }),

/***/ "6b89":
/***/ (function(module, exports, __webpack_require__) {

// extracted by mini-css-extract-plugin

/***/ }),

/***/ "8c16":
/***/ (function(module, exports, __webpack_require__) {

module.exports = __webpack_require__.p + "static/img/title-parameterService.93ef9f67.png";

/***/ }),

/***/ "a2b6":
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "b", function() { return queryParamList; });
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return getParamInfo; });
/* harmony import */ var _utils_request_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__("b775");

// 获取参数列表
function queryParamList(query) {
  return Object(_utils_request_js__WEBPACK_IMPORTED_MODULE_0__[/* default */ "a"])({
    url: '/ociswebserver/ocis/openParam/queryParamList',
    method: 'get',
    params: query
  });
}

// 获取参数详情
function getParamInfo(query) {
  return Object(_utils_request_js__WEBPACK_IMPORTED_MODULE_0__[/* default */ "a"])({
    url: '/ociswebserver/ocis/openParam/queryParamDetailPage',
    method: 'get',
    params: query
  });
}

/***/ }),

/***/ "b147":
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
// ESM COMPAT FLAG
__webpack_require__.r(__webpack_exports__);

// CONCATENATED MODULE: ./node_modules/cache-loader/dist/cjs.js?{"cacheDirectory":"node_modules/.cache/vue-loader","cacheIdentifier":"70cf6009-vue-loader-template"}!./node_modules/vue-loader/lib/loaders/templateLoader.js??vue-loader-options!./node_modules/cache-loader/dist/cjs.js??ref--0-0!./node_modules/vue-loader/lib??vue-loader-options!./src/views/tgcs/info.vue?vue&type=template&id=5a6d31e0&scoped=true
var render = function () {var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"wrap-box"},[_c('div',{staticClass:"wrap-info"},[_vm._m(0),_c('div',{staticClass:"wrap-info-content"},[_c('el-row',[_c('el-col',{attrs:{"xs":24,"sm":24,"md":5,"lg":5,"xl":5}},[_c('el-input',{staticStyle:{"padding":"2px 20px"},attrs:{"placeholder":"输入参数名称快速定位","size":"small"},on:{"input":_vm.handleSearch},model:{value:(_vm.filterText),callback:function ($$v) {_vm.filterText=$$v},expression:"filterText"}}),_c('el-scrollbar',[_c('div',{staticClass:"left-tab"},[_c('ul',_vm._l((_vm.dataList),function(item){return _c('li',{key:item.paramCode,class:{ active: item.paramCode == _vm.currentCode },on:{"click":function($event){return _vm.handleChangeTab(item)}}},[_c('p',[_vm._v(_vm._s(item.paramName))])])}),0)])])],1),_c('el-col',{attrs:{"xs":24,"sm":24,"md":19,"lg":19,"xl":19}},[_c('div',{staticClass:"right-list"},[_c('div',{staticClass:"top"},[_c('el-row',[_c('el-col',{attrs:{"xs":24,"sm":24,"md":24,"lg":14,"xl":14}},[_c('p',{staticClass:"name"},[_vm._v(_vm._s(_vm.currentName))])]),_c('el-col',{staticStyle:{"padding":"2px"},attrs:{"xs":24,"sm":24,"md":24,"lg":10,"xl":10}},[_c('el-input',{staticClass:"input-with-select",attrs:{"placeholder":"请输入内容","clearable":""},model:{value:(_vm.query.colValue),callback:function ($$v) {_vm.$set(_vm.query, "colValue", $$v)},expression:"query.colValue"}},[_c('el-select',{attrs:{"slot":"prepend","placeholder":"请选择","title":_vm.getTitle(_vm.query.colCode),"clearable":""},slot:"prepend",model:{value:(_vm.query.colCode),callback:function ($$v) {_vm.$set(_vm.query, "colCode", $$v)},expression:"query.colCode"}},_vm._l((_vm.dataColumn),function(item){return _c('el-option',{key:item.colAlias,attrs:{"value":item.colAlias,"label":item.colName}})}),1),_c('el-button',{attrs:{"slot":"append","icon":"el-icon-search"},on:{"click":_vm.dataSearch},slot:"append"})],1)],1),_c('el-col',{directives:[{name:"show",rawName:"v-show",value:(_vm.currentNote),expression:"currentNote"}],attrs:{"xs":24,"sm":24,"md":24,"lg":24,"xl":24}},[_c('p',{staticClass:"parameter-detail-title"},[_vm._v(_vm._s(_vm.currentNote))])])],1)],1),_c('div',[_c('el-table',{directives:[{name:"loading",rawName:"v-loading",value:(_vm.loading),expression:"loading"}],staticStyle:{"width":"100%","margin-bottom":"20px"},attrs:{"stripe":"","data":_vm.tableData,"header-cell-style":{
                  fontSize: '14px',
                  backgroundColor: '#16407a',
                  color: '#fff',
                },"height":_vm.tableHeight}},_vm._l((_vm.dataColumn),function(item){return _c('el-table-column',{key:item.colAlias,attrs:{"label":item.colName},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_vm._v(" "+_vm._s(_vm.getValueIgnoreCase(scope.row, item.colAlias))+" ")]}}],null,true)})}),1),_c('div',{staticClass:"hidden-sm-and-down"},[_c('el-pagination',{attrs:{"current-page":_vm.query.offset,"page-sizes":[10, 20, 50, 100],"page-size":_vm.query.limit,"layout":"total, sizes, prev, pager, next, jumper","total":_vm.total},on:{"size-change":_vm.handleSizeChange,"current-change":_vm.handleCurrentChange}})],1),_c('div',{staticClass:"hidden-md-and-up",staticStyle:{"text-align":"center"}},[_c('el-pagination',{attrs:{"small":"","layout":"prev,pager, next","total":_vm.total,"background":""},on:{"size-change":_vm.handleSizeChange,"current-change":_vm.handleCurrentChange}})],1)],1)])])],1)],1)])])}
var staticRenderFns = [function () {var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"wrap-info-title"},[_c('img',{attrs:{"src":__webpack_require__("8c16"),"alt":""}})])}]


// CONCATENATED MODULE: ./src/views/tgcs/info.vue?vue&type=template&id=5a6d31e0&scoped=true

// EXTERNAL MODULE: ./node_modules/core-js/modules/es.array.push.js
var es_array_push = __webpack_require__("14d9");

// EXTERNAL MODULE: ./node_modules/core-js/modules/esnext.iterator.constructor.js
var esnext_iterator_constructor = __webpack_require__("0643");

// EXTERNAL MODULE: ./node_modules/core-js/modules/esnext.iterator.filter.js
var esnext_iterator_filter = __webpack_require__("2382");

// EXTERNAL MODULE: ./src/api/tgcs/index.js
var tgcs = __webpack_require__("a2b6");

// EXTERNAL MODULE: ./src/mixins/index.js
var mixins = __webpack_require__("1b62");

// CONCATENATED MODULE: ./node_modules/cache-loader/dist/cjs.js??ref--12-0!./node_modules/thread-loader/dist/cjs.js!./node_modules/babel-loader/lib!./node_modules/cache-loader/dist/cjs.js??ref--0-0!./node_modules/vue-loader/lib??vue-loader-options!./src/views/tgcs/info.vue?vue&type=script&lang=js



//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//
//



/* harmony default export */ var infovue_type_script_lang_js = ({
  name: "mySearch",
  mixins: [mixins["a" /* mixinCommon */]],
  data() {
    return {
      filterText: "",
      // 当前选中编码
      currentCode: "",
      // 当前选中名称
      currentName: "",
      // 适用说明信息
      currentNote: "",
      form: {},
      // 参数条件
      query: {
        offset: 1,
        limit: 10,
        colCode: "",
        colValue: ""
      },
      total: 0,
      // 参数名列表
      dataList: [],
      originDataList: [],
      // 参数详情表头，及查询参数类型
      dataColumn: [],
      // 参数详情表格数据
      tableData: [],
      loading: true,
      tableHeight: 500
    };
  },
  created() {
    // 设置页面标题
    document.title = "海关政务服务通关参数详情";
  },
  async mounted() {
    this.nowDataRMFT(() => {
      this.getData();
    });
  },
  watch: {
    '$route.query.paramCode': {
      handler(val) {
        this.$nextTick(() => {
          if (this.isMobile()) {
            //console.log('移动端');
          } else {
            //console.log('PC');
            this.tableHeight = 546;
            const scHt = document.querySelector('.parameter-detail-title').offsetHeight;
            if (this.currentNote) {
              this.tableHeight = this.tableHeight - Number(scHt) - 10;
            } else {
              this.tableHeight = 546;
            }
          }
        });
      },
      immediate: true
    }
  },
  methods: {
    isMobile() {
      return /(phone|pad|pod|iPhone|iPod|ios|iPad|Android|Mobile|BlackBerry|IEMobile|MQQBrowser|JUC|Fennec|wOSBrowser|BrowserNG|WebOS|Symbian|Windows Phone)/i.test(navigator.userAgent);
    },
    handleSearch() {
      let result = this.originDataList.filter(item => {
        return item.paramName != '' && item.paramName.indexOf(this.filterText) != -1;
      });
      this.dataList = result;
    },
    dataSearch() {
      if (!this.query.colCode) {
        this.$message.error(`请选择过滤项`);
        return;
      }
      this.query.offset = 1;
      this.getInfoData();
    },
    getTitle(val) {
      if (val != "") {
        let colObj = this.dataColumn.filter(item => item.colAlias == val);
        return colObj[0].colName;
      }
    },
    // 页码切换
    handleCurrentChange(value) {
      this.query.offset = value;
      this.getInfoData();
    },
    handleSizeChange(value) {
      this.query.offset = 1;
      this.query.limit = value;
      this.getInfoData();
    },
    // 获取参数列表
    getData() {
      Object(tgcs["b" /* queryParamList */])().then(res => {
        const resultdata = this.getResponseData(res);
        if (resultdata.ok) {
          this.dataList = Array.isArray(resultdata.data) ? resultdata.data : [];
          this.originDataList = Array.isArray(resultdata.data) ? resultdata.data : [];
          //设置选中项并且请求参数详情列表
          this.currentCode = this.$route.query.paramCode ? this.$route.query.paramCode : this.dataList[0].paramCode;
          // 设置选中参数名称
          this.currentName = this.dataList.filter(e => {
            return e.paramCode == this.currentCode;
          })[0].paramName;
          //设置当前适用说明
          this.currentNote = this.dataList.filter(e => {
            return e.paramCode == this.currentCode;
          })[0].note;
          this.getInfoData();
        }
      }).catch(err => {
        this.dataList = [];
        this.originDataList = [];
      });
    },
    handleChangeTab(item) {
      this.currentCode = item.paramCode;
      this.currentName = item.paramName;
      this.currentNote = item.note;
      this.query.offset = 1;
      this.query.colCode = "";
      this.query.colValue = "";
      this.getInfoData();
      this.$router.push({
        path: "/tgcs/info",
        query: {
          paramCode: item.paramCode
        }
      });
    },
    // 获取参数详情列表数据
    getInfoData() {
      let params = Object.assign({}, this.query, {
        paramCode: this.currentCode
      });
      params.offset = params.offset - 1;
      this.loading = true;
      Object(tgcs["a" /* getParamInfo */])(params).then(res => {
        const resultdata = this.getResponseData(res);
        this.dataColumn = resultdata.data.header;
        this.tableData = resultdata.data.rows;
        this.total = resultdata.data.count;
        this.loading = false;
      }).catch(err => {
        this.dataColumn = resultdata.data.header;
        this.tableData = [];
        this.total = 0;
        this.loading = false;
      });
    },
    // 引入解密方法
    nowDataRMFT(callback) {
      let num = Math.floor(Math.random() * 9 + 1);
      let baseUrl = window.location.href.indexOf("ociswebserver") != -1 ? "/" : "/dev-api/";
      let script = document.createElement("script");
      script.type = "text/javascript";
      script.src = `${baseUrl}ociswebserver/menuManger?a=${num}`;
      let script1 = document.createElement("script");
      script1.type = "text/javascript";
      script1.src = `${baseUrl}ociswebserver/static/js/Mu64.js`;
      document.getElementsByTagName("head")[0].appendChild(script);
      document.getElementsByTagName("head")[0].appendChild(script1);
      script.onload = function () {
        if (callback) callback();
      };
      script.onerror = function () {
        if (callback) callback();
      };
    },
    // 调用解密方法
    getResponseData(res) {
      let resDesString = res;
      if (resDesString.startsWith('"')) {
        resDesString = resDesString.substring(1, resDesString.length - 1);
      }
      // 解密
      let responseData = JSON.parse(loadAESDecryptStr(resDesString));
      return responseData;
    },
    getValueIgnoreCase(jsonObj, targetKey) {
      if (jsonObj[targetKey] == undefined) {
        targetKey = targetKey.toLowerCase();
        for (let key in jsonObj) {
          if (jsonObj.hasOwnProperty(key) && key.toLowerCase() === targetKey) {
            return jsonObj[key];
          }
        }
        return '';
      } else {
        return jsonObj[targetKey];
      }
    }
  }
});
// CONCATENATED MODULE: ./src/views/tgcs/info.vue?vue&type=script&lang=js
 /* harmony default export */ var tgcs_infovue_type_script_lang_js = (infovue_type_script_lang_js); 
// EXTERNAL MODULE: ./src/views/tgcs/info.vue?vue&type=style&index=0&id=5a6d31e0&prod&scoped=true&lang=scss
var infovue_type_style_index_0_id_5a6d31e0_prod_scoped_true_lang_scss = __webpack_require__("b706");

// EXTERNAL MODULE: ./node_modules/vue-loader/lib/runtime/componentNormalizer.js
var componentNormalizer = __webpack_require__("2877");

// CONCATENATED MODULE: ./src/views/tgcs/info.vue






/* normalize component */

var component = Object(componentNormalizer["a" /* default */])(
  tgcs_infovue_type_script_lang_js,
  render,
  staticRenderFns,
  false,
  null,
  "5a6d31e0",
  null
  
)

/* harmony default export */ var info = __webpack_exports__["default"] = (component.exports);

/***/ }),

/***/ "b706":
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony import */ var _node_modules_mini_css_extract_plugin_dist_loader_js_ref_8_oneOf_1_0_node_modules_css_loader_dist_cjs_js_ref_8_oneOf_1_1_node_modules_vue_loader_lib_loaders_stylePostLoader_js_node_modules_postcss_loader_src_index_js_ref_8_oneOf_1_2_node_modules_sass_loader_dist_cjs_js_ref_8_oneOf_1_3_node_modules_cache_loader_dist_cjs_js_ref_0_0_node_modules_vue_loader_lib_index_js_vue_loader_options_info_vue_vue_type_style_index_0_id_5a6d31e0_prod_scoped_true_lang_scss__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__("6b89");
/* harmony import */ var _node_modules_mini_css_extract_plugin_dist_loader_js_ref_8_oneOf_1_0_node_modules_css_loader_dist_cjs_js_ref_8_oneOf_1_1_node_modules_vue_loader_lib_loaders_stylePostLoader_js_node_modules_postcss_loader_src_index_js_ref_8_oneOf_1_2_node_modules_sass_loader_dist_cjs_js_ref_8_oneOf_1_3_node_modules_cache_loader_dist_cjs_js_ref_0_0_node_modules_vue_loader_lib_index_js_vue_loader_options_info_vue_vue_type_style_index_0_id_5a6d31e0_prod_scoped_true_lang_scss__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_node_modules_mini_css_extract_plugin_dist_loader_js_ref_8_oneOf_1_0_node_modules_css_loader_dist_cjs_js_ref_8_oneOf_1_1_node_modules_vue_loader_lib_loaders_stylePostLoader_js_node_modules_postcss_loader_src_index_js_ref_8_oneOf_1_2_node_modules_sass_loader_dist_cjs_js_ref_8_oneOf_1_3_node_modules_cache_loader_dist_cjs_js_ref_0_0_node_modules_vue_loader_lib_index_js_vue_loader_options_info_vue_vue_type_style_index_0_id_5a6d31e0_prod_scoped_true_lang_scss__WEBPACK_IMPORTED_MODULE_0__);
/* unused harmony reexport * */


/***/ })

}]);