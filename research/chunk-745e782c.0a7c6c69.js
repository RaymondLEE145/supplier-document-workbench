(window["webpackJsonp"] = window["webpackJsonp"] || []).push([["chunk-745e782c"],{

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

/***/ "1db5":
/***/ (function(module, exports, __webpack_require__) {

// extracted by mini-css-extract-plugin

/***/ }),

/***/ "393f":
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
// ESM COMPAT FLAG
__webpack_require__.r(__webpack_exports__);

// CONCATENATED MODULE: ./node_modules/cache-loader/dist/cjs.js?{"cacheDirectory":"node_modules/.cache/vue-loader","cacheIdentifier":"70cf6009-vue-loader-template"}!./node_modules/vue-loader/lib/loaders/templateLoader.js??vue-loader-options!./node_modules/cache-loader/dist/cjs.js??ref--0-0!./node_modules/vue-loader/lib??vue-loader-options!./src/views/tgcs/index.vue?vue&type=template&id=13064a64&scoped=true
var render = function () {var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"wrap-box"},[_c('div',{staticClass:"wrap-info"},[_vm._m(0),_c('div',{staticStyle:{"padding":"10px 10px 10px 10px"}},[_c('el-row',[_c('el-col',{staticStyle:{"float":"right"},attrs:{"xs":24,"sm":24,"md":8,"lg":8,"xl":8}},[_c('el-input',{attrs:{"placeholder":"请输入您要查询的参数","clearable":""},model:{value:(_vm.keyWords),callback:function ($$v) {_vm.keyWords=$$v},expression:"keyWords"}},[_c('el-button',{staticStyle:{"border-radius":"0 4px 4px 0"},attrs:{"slot":"append","icon":"el-icon-search","type":"confirm"},slot:"append"})],1)],1)],1)],1),_c('div',{staticClass:"wrap-info-content"},[(_vm.loading)?_c('div',{staticClass:"loading-container"},[_c('el-skeleton',{attrs:{"rows":6,"animated":""}})],1):_c('div',{staticClass:"wrap-info-item"},_vm._l((_vm.dataList),function(item){return _c('div',{directives:[{name:"show",rawName:"v-show",value:(_vm.handleIsShowItem(item)),expression:"handleIsShowItem(item)"}],key:item.paramCode,staticClass:"service-item-publice",on:{"click":function($event){return _vm.toInfo(item)}}},[_c('div',{attrs:{"title":item.paramName}},[_vm._v(" "+_vm._s(item.paramName)+" ")])])}),0),_c('el-empty',{directives:[{name:"show",rawName:"v-show",value:(!_vm.loading && (
              _vm.dataList.length == 0 ||
                !_vm.dataList.some(function (s) {
                  return _vm.handleIsShowItem(s);
                })
            )),expression:"!loading && (\n              dataList.length == 0 ||\n                !dataList.some(s => {\n                  return handleIsShowItem(s);\n                })\n            )"}],attrs:{"description":"未查询到相关数据"}})],1)])])}
var staticRenderFns = [function () {var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"wrap-info-title"},[_c('img',{attrs:{"src":__webpack_require__("8c16"),"alt":""}})])}]


// CONCATENATED MODULE: ./src/views/tgcs/index.vue?vue&type=template&id=13064a64&scoped=true

// EXTERNAL MODULE: ./src/api/tgcs/index.js
var tgcs = __webpack_require__("a2b6");

// EXTERNAL MODULE: ./src/mixins/index.js
var mixins = __webpack_require__("1b62");

// CONCATENATED MODULE: ./node_modules/cache-loader/dist/cjs.js??ref--12-0!./node_modules/thread-loader/dist/cjs.js!./node_modules/babel-loader/lib!./node_modules/cache-loader/dist/cjs.js??ref--0-0!./node_modules/vue-loader/lib??vue-loader-options!./src/views/tgcs/index.vue?vue&type=script&lang=js
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



/* harmony default export */ var tgcsvue_type_script_lang_js = ({
  name: "tgcsIndex",
  mixins: [mixins["a" /* mixinCommon */]],
  data() {
    return {
      keyWords: '',
      dataList: [],
      loading: true
    };
  },
  created() {
    // 设置页面标题
    document.title = "海关政务服务通关参数";
  },
  mounted() {
    this.nowDataRMFT(() => {
      this.getData();
    });
    this.adjustcontentHeight();
  },
  methods: {
    adjustcontentHeight() {
      // 获取 header、content 和 footer 元素
      const headerElement = document.querySelector('.header');
      const contentElement = document.querySelector('.wrap-box');
      const footerElement = document.querySelector('.footer--');

      // 获取视口高度
      const windowHeight = window.innerHeight;

      // 获取 header 和 footer 的高度
      const headerHeight = headerElement.offsetHeight;
      const footerHeight = footerElement.offsetHeight;

      // 计算 content 的高度
      const contentHeight = windowHeight - headerHeight - footerHeight;

      // 设置 content 元素的最小高度为计算得到的高度
      contentElement.style.minHeight = `${contentHeight}px`;
    },
    handleIsShowItem(item) {
      if (this.keyWords == "" || item.paramName.indexOf(this.keyWords) != -1) {
        return true;
      } else {
        return false;
      }
    },
    getData() {
      this.loading = true;
      Object(tgcs["b" /* queryParamList */])().then(res => {
        const resultdata = this.getResponseData(res);
        if (resultdata.ok) {
          this.dataList = Array.isArray(resultdata.data) ? resultdata.data : [];
        }
      }).catch(err => {
        this.dataList = [];
        //console.log("66666"+err)
      }).finally(() => {
        this.loading = false;
      });
    },
    toInfo(item) {
      const routeData = this.$router.resolve({
        path: "/tgcs/info",
        query: {
          paramCode: item.paramCode
        }
      });
      window.open(routeData.href, '_blank');
      //this.$router.push({
      //  path: "/tgcs/info",
      //  query: {
      //    paramCode: item.paramCode,
      //  },
      //});
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
    }
  }
});
// CONCATENATED MODULE: ./src/views/tgcs/index.vue?vue&type=script&lang=js
 /* harmony default export */ var views_tgcsvue_type_script_lang_js = (tgcsvue_type_script_lang_js); 
// EXTERNAL MODULE: ./src/views/tgcs/index.vue?vue&type=style&index=0&id=13064a64&prod&scoped=true&lang=scss
var tgcsvue_type_style_index_0_id_13064a64_prod_scoped_true_lang_scss = __webpack_require__("a435");

// EXTERNAL MODULE: ./node_modules/vue-loader/lib/runtime/componentNormalizer.js
var componentNormalizer = __webpack_require__("2877");

// CONCATENATED MODULE: ./src/views/tgcs/index.vue






/* normalize component */

var component = Object(componentNormalizer["a" /* default */])(
  views_tgcsvue_type_script_lang_js,
  render,
  staticRenderFns,
  false,
  null,
  "13064a64",
  null
  
)

/* harmony default export */ var views_tgcs = __webpack_exports__["default"] = (component.exports);

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

/***/ "a435":
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony import */ var _node_modules_mini_css_extract_plugin_dist_loader_js_ref_8_oneOf_1_0_node_modules_css_loader_dist_cjs_js_ref_8_oneOf_1_1_node_modules_vue_loader_lib_loaders_stylePostLoader_js_node_modules_postcss_loader_src_index_js_ref_8_oneOf_1_2_node_modules_sass_loader_dist_cjs_js_ref_8_oneOf_1_3_node_modules_cache_loader_dist_cjs_js_ref_0_0_node_modules_vue_loader_lib_index_js_vue_loader_options_index_vue_vue_type_style_index_0_id_13064a64_prod_scoped_true_lang_scss__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__("1db5");
/* harmony import */ var _node_modules_mini_css_extract_plugin_dist_loader_js_ref_8_oneOf_1_0_node_modules_css_loader_dist_cjs_js_ref_8_oneOf_1_1_node_modules_vue_loader_lib_loaders_stylePostLoader_js_node_modules_postcss_loader_src_index_js_ref_8_oneOf_1_2_node_modules_sass_loader_dist_cjs_js_ref_8_oneOf_1_3_node_modules_cache_loader_dist_cjs_js_ref_0_0_node_modules_vue_loader_lib_index_js_vue_loader_options_index_vue_vue_type_style_index_0_id_13064a64_prod_scoped_true_lang_scss__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_node_modules_mini_css_extract_plugin_dist_loader_js_ref_8_oneOf_1_0_node_modules_css_loader_dist_cjs_js_ref_8_oneOf_1_1_node_modules_vue_loader_lib_loaders_stylePostLoader_js_node_modules_postcss_loader_src_index_js_ref_8_oneOf_1_2_node_modules_sass_loader_dist_cjs_js_ref_8_oneOf_1_3_node_modules_cache_loader_dist_cjs_js_ref_0_0_node_modules_vue_loader_lib_index_js_vue_loader_options_index_vue_vue_type_style_index_0_id_13064a64_prod_scoped_true_lang_scss__WEBPACK_IMPORTED_MODULE_0__);
/* unused harmony reexport * */


/***/ })

}]);