//@ts-ignore
import { api } from "../../scripts/api.js";

setTimeout(() => {
  import(api.api_base + "/inner_enhance_web/input.js");
}, 500);
