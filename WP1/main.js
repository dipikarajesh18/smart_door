function sub(name, number) 
{
    // var name = document.getElementById("name").value;
    // var number = document.getElementById("number").value;
    // var input = name + number; 	
    var apigClient = apigClientFactory.newClient();
	let params = {};
    let additionalParams = {};
    // console.log("This is the input : ",input)
	var body = {
        "name" : name,
        "number" : number
    };
    apigClient.visitorinfoPost(params, body)
    .then(result=>{
        console.log("Success")
        alert("Sent OTP to visitor!");
    })
    .catch(err=>{
        console.log(err)
    })
}