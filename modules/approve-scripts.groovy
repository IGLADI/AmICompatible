// based on https://stackoverflow.com/questions/43699190/seed-job-asks-for-script-approval-in-jenkins#:~:text=If%20you%27re%20using%20the%20Jenkins%20Groovy%20DSL%2C%20here%27s%20a%20snippet%20you%20can%20use%20to%20approve%20every%20script%20that%27s%20pending%3A
import org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval

ScriptApproval scriptApproval = ScriptApproval.get()
scriptApproval.pendingScripts.each {
    scriptApproval.approveScript(it.hash)
}
